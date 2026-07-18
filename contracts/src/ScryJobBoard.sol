// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IScryArbiter} from "./IScryArbiter.sol";
import {IERC20} from "./IERC20.sol";

interface IReputation {
    function earn(address who, uint256 amount, bytes32 reason) external;
    function slash(address who, uint256 amount, bytes32 reason) external;
    function meets(address who) external view returns (bool);
}

interface IInsurancePool {
    function claim(address to, uint256 amount, uint256 jobId) external returns (uint256);
}

/// @title ScryJobBoard — hire a named worker for a task, with a trust mode
/// @notice The on-chain spine of the agent-labor economy (AGENT-ECONOMY.md).
///         A buyer hires a named seller for a task carrying a HASHED completion
///         criterion and a deadline, under one of three trust modes:
///
///           - Escrow          buyer locks the amount; released on completion,
///                             refunded on timeout. Full protection both ways.
///           - Insured         buyer locks nothing but pays a premium to the
///                             pool; on buyer default the seller is covered
///                             from the pool (capped). Capital-lite.
///           - ReputationOnly  nothing locked; seller must meet the rep
///                             threshold; default just slashes soulbound rep.
///
///         Disputes go to an arbiter that is paid a FLAT fee INDEPENDENT of its
///         verdict (the anti-Bar-Hadya guarantee, in code). The house takes a
///         posted fee off each sale to the splitter; completion earns soulbound
///         rep, default/adverse rulings slash it. Money moves labor, coverage,
///         and fees — never a measurement, never a ruling.
///
///         No owner-drain: job funds only ever move along a job's own outcome.
contract ScryJobBoard {
    enum Mode { Escrow, Insured, ReputationOnly }
    enum Status { None, Posted, Delivered, Closed }

    struct Job {
        address buyer;
        address seller;
        uint256 amount; // $SCRY paid to the seller on completion (pre-fee)
        Mode mode;
        Status status;
        bytes32 specHash; // the committed completion criterion — the court rules vs THIS
        bytes32 deliveredHash;
        uint64 deadline;
    }

    IERC20 public immutable scry;
    IReputation public immutable rep;
    IInsurancePool public insurancePool;
    address public feeSplitter; // ScryFeeSplitter — every sale's cut lands here
    IScryArbiter public arbiter;
    address public operator;

    uint16 public feeBps = 500; // 5%, posted; capped at 10%
    uint256 public repReward = 10; // rep earned on an honest completion
    uint256 public repPenalty = 25; // rep slashed on default / adverse ruling

    Job[] public jobs;

    event Posted(uint256 indexed id, address indexed buyer, address indexed seller, uint256 amount, Mode mode, bytes32 specHash, uint64 deadline);
    event Delivered(uint256 indexed id, bytes32 deliveredHash);
    event Closed(uint256 indexed id, bytes32 outcome, uint256 toSeller, uint256 fee);
    event Ruled(uint256 indexed id, IScryArbiter.Verdict verdict);
    event ParamSet(bytes32 what, uint256 value);

    modifier onlyOperator() {
        require(msg.sender == operator, "not operator");
        _;
    }

    constructor(IERC20 _scry, IReputation _rep, IInsurancePool _pool, address _feeSplitter, IScryArbiter _arbiter) {
        scry = _scry;
        rep = _rep;
        insurancePool = _pool;
        feeSplitter = _feeSplitter;
        arbiter = _arbiter;
        operator = msg.sender;
    }

    // ── post ─────────────────────────────────────────────────────────────
    function post(address seller, uint256 amount, Mode mode, bytes32 specHash, uint64 deadline, uint256 premium)
        external
        returns (uint256 id)
    {
        require(seller != address(0) && seller != msg.sender, "bad seller");
        require(amount > 0 && specHash != bytes32(0), "bad job");
        require(deadline > block.timestamp, "deadline passed");
        if (mode == Mode.ReputationOnly) require(rep.meets(seller), "seller below rep threshold");
        if (mode == Mode.Escrow) {
            require(scry.transferFrom(msg.sender, address(this), amount), "escrow pull failed");
        } else if (mode == Mode.Insured) {
            require(premium > 0, "premium required");
            require(scry.transferFrom(msg.sender, address(insurancePool), premium), "premium pull failed");
        }
        id = jobs.length;
        jobs.push(Job(msg.sender, seller, amount, mode, Status.Posted, specHash, bytes32(0), deadline));
        emit Posted(id, msg.sender, seller, amount, mode, specHash, deadline);
    }

    // ── deliver ──────────────────────────────────────────────────────────
    function deliver(uint256 id, bytes32 deliveredHash) external {
        Job storage j = jobs[id];
        require(msg.sender == j.seller, "not seller");
        require(j.status == Status.Posted, "not open");
        j.deliveredHash = deliveredHash;
        j.status = Status.Delivered;
        emit Delivered(id, deliveredHash);
    }

    // ── complete (buyer confirms the delivery meets the spec) ────────────
    function complete(uint256 id) external {
        Job storage j = jobs[id];
        require(msg.sender == j.buyer, "not buyer");
        require(j.status == Status.Delivered, "not delivered");
        j.status = Status.Closed; // checks-effects: close before paying
        _payoutSeller(j, id, false);
    }

    // ── close after deadline (no human needed) ───────────────────────────
    /// Anyone may call once the deadline passes:
    ///   - not delivered  → seller defaulted → refund/settle to buyer, slash seller
    ///   - delivered      → buyer went silent → seller is paid/covered, slash buyer
    function close(uint256 id) external {
        Job storage j = jobs[id];
        require(j.status == Status.Posted || j.status == Status.Delivered, "closed");
        require(block.timestamp >= j.deadline, "not yet");
        if (j.status == Status.Posted) {
            j.status = Status.Closed;
            _refundBuyer(j, id, "seller-default");
            rep.slash(j.seller, repPenalty, "seller-default");
        } else {
            j.status = Status.Closed;
            _payoutSeller(j, id, true); // buyer silent on a delivered job → seller made whole
            rep.slash(j.buyer, repPenalty, "buyer-default");
        }
    }

    // ── dispute → the flat-fee court ─────────────────────────────────────
    function dispute(uint256 id) external {
        Job storage j = jobs[id];
        require(msg.sender == j.buyer || msg.sender == j.seller, "not a party");
        require(j.status == Status.Posted || j.status == Status.Delivered, "closed");

        // Guarantee §9.1: the arbiter is paid a FLAT fee BEFORE ruling, from
        // the party opening the case, identical whatever the verdict.
        uint256 fee = arbiter.flatFee();
        if (fee > 0) require(scry.transferFrom(msg.sender, arbiter.feeRecipient(), fee), "arb fee failed");

        IScryArbiter.Verdict v = arbiter.rule(id, j.specHash, j.deliveredHash);
        emit Ruled(id, v);
        j.status = Status.Closed;

        if (v == IScryArbiter.Verdict.ForSeller) {
            _payoutSeller(j, id, true); // deliverable met the committed spec
        } else {
            // ForBuyer or Undecided → refund/settle to buyer, slash the seller
            _refundBuyer(j, id, "ruled-for-buyer");
            rep.slash(j.seller, repPenalty, "ruled-for-buyer");
        }
    }

    // ── internals: the only paths funds may take ─────────────────────────
    function _payoutSeller(Job storage j, uint256 id, bool coverIfUnfunded) internal {
        uint256 fee = (j.amount * feeBps) / 10_000;
        uint256 net = j.amount - fee;
        if (j.mode == Mode.Escrow) {
            require(scry.transfer(j.seller, net), "pay seller failed");
            if (fee > 0) require(scry.transfer(feeSplitter, fee), "fee failed");
        } else {
            // Insured / ReputationOnly: the amount was never escrowed. Try to
            // pull it from the buyer now (voluntary completion path)…
            bool pulled = _tryPull(j.buyer, address(this), j.amount);
            if (pulled) {
                require(scry.transfer(j.seller, net), "pay seller failed");
                if (fee > 0) require(scry.transfer(feeSplitter, fee), "fee failed");
            } else if (coverIfUnfunded && j.mode == Mode.Insured) {
                // …else, on buyer default, make the seller whole from the pool.
                insurancePool.claim(j.seller, net, id);
            }
            // ReputationOnly with a defaulting buyer: no capital recovery — the
            // seller ate the loss; the buyer's rep was slashed by the caller.
        }
        rep.earn(j.seller, repReward, "completed");
        emit Closed(id, "completed", net, fee);
    }

    function _refundBuyer(Job storage j, uint256 id, bytes32 reason) internal {
        if (j.mode == Mode.Escrow) {
            require(scry.transfer(j.buyer, j.amount), "refund failed");
        }
        // Insured / ReputationOnly: nothing was locked, nothing to refund.
        emit Closed(id, reason, 0, 0);
    }

    function _tryPull(address from, address to, uint256 amount) internal returns (bool) {
        (bool ok, bytes memory ret) =
            address(scry).call(abi.encodeWithSelector(IERC20.transferFrom.selector, from, to, amount));
        return ok && (ret.length == 0 || abi.decode(ret, (bool)));
    }

    // ── operator knobs (params only; never a fund path) ──────────────────
    function setFeeBps(uint16 bps) external onlyOperator {
        require(bps <= 1_000, "fee > 10%");
        feeBps = bps;
        emit ParamSet("feeBps", bps);
    }

    function setRepRewards(uint256 reward, uint256 penalty) external onlyOperator {
        repReward = reward;
        repPenalty = penalty;
        emit ParamSet("repReward", reward);
        emit ParamSet("repPenalty", penalty);
    }

    function setArbiter(IScryArbiter _arbiter) external onlyOperator {
        arbiter = _arbiter;
        emit ParamSet("arbiter", uint256(uint160(address(_arbiter))));
    }

    function setFeeSplitter(address _s) external onlyOperator {
        require(_s != address(0), "zero");
        feeSplitter = _s;
        emit ParamSet("feeSplitter", uint256(uint160(_s)));
    }

    function jobCount() external view returns (uint256) {
        return jobs.length;
    }
}
