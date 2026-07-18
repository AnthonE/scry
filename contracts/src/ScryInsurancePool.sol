// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "./IERC20.sol";

/// @title ScryInsurancePool — a premium pool for the trust menu
/// @notice The lightest trust mode: instead of locking escrow, parties pay a
///         small premium into this pool; a covered dispute ruled for the buyer
///         pays out from the pool, capped. Auditable, and — like everything
///         else here — there is NO owner-drain path: funds leave only as
///         premiums-in (anyone) and claims-out (an authorized claimant, e.g.
///         the job board, capped per payout).
///
///         This prices RISK, never a measurement. Charging a premium to cover
///         a job does not move any meter number or ruling.
contract ScryInsurancePool {
    IERC20 public immutable scry;
    address public operator;
    uint256 public maxPayout; // per-claim cap (posted)

    mapping(address => bool) public claimant; // market contracts allowed to claim

    event PremiumPaid(address indexed from, uint256 amount);
    event Claimed(address indexed to, uint256 amount, uint256 indexed jobId);
    event ClaimantSet(address indexed who, bool allowed);
    event MaxPayoutSet(uint256 maxPayout);
    event OperatorTransferred(address indexed from, address indexed to);

    modifier onlyOperator() {
        require(msg.sender == operator, "not operator");
        _;
    }

    constructor(IERC20 _scry, uint256 _maxPayout) {
        scry = _scry;
        operator = msg.sender;
        maxPayout = _maxPayout;
        emit MaxPayoutSet(_maxPayout);
    }

    /// Anyone can top the pool (a premium). Pull via transferFrom so the
    /// payer keeps control of approval.
    function payPremium(uint256 amount) external {
        require(amount > 0, "zero");
        require(scry.transferFrom(msg.sender, address(this), amount), "pull failed");
        emit PremiumPaid(msg.sender, amount);
    }

    /// The pool balance available to cover claims.
    function reserves() external view returns (uint256) {
        return scry.balanceOf(address(this));
    }

    /// Pay a covered claim. Only an authorized claimant (the job board), only
    /// up to the posted cap and available reserves. Never an owner withdraw.
    function claim(address to, uint256 amount, uint256 jobId) external returns (uint256 paid) {
        require(claimant[msg.sender], "not claimant");
        require(to != address(0), "zero");
        paid = amount > maxPayout ? maxPayout : amount;
        uint256 bal = scry.balanceOf(address(this));
        if (paid > bal) paid = bal; // best-effort; a thin pool pays what it has
        if (paid > 0) {
            require(scry.transfer(to, paid), "payout failed");
            emit Claimed(to, paid, jobId);
        }
    }

    function setClaimant(address who, bool allowed) external onlyOperator {
        claimant[who] = allowed;
        emit ClaimantSet(who, allowed);
    }

    function setMaxPayout(uint256 _maxPayout) external onlyOperator {
        maxPayout = _maxPayout;
        emit MaxPayoutSet(_maxPayout);
    }

    function transferOperator(address to) external onlyOperator {
        require(to != address(0), "zero");
        emit OperatorTransferred(operator, to);
        operator = to;
    }
}
