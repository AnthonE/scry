// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/ScryReputation.sol";
import "../src/ScryInsurancePool.sol";
import "../src/ScryJobBoard.sol";
import "../src/IScryArbiter.sol";

/// Minimal ERC-20 standing in for the fair-launched $SCRY.
contract MockSCRY {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 a) external { balanceOf[to] += a; }
    function transfer(address to, uint256 a) external returns (bool) {
        require(balanceOf[msg.sender] >= a, "bal");
        balanceOf[msg.sender] -= a; balanceOf[to] += a; return true;
    }
    function transferFrom(address f, address t, uint256 a) external returns (bool) {
        require(allowance[f][msg.sender] >= a, "allow");
        require(balanceOf[f] >= a, "bal");
        allowance[f][msg.sender] -= a; balanceOf[f] -= a; balanceOf[t] += a; return true;
    }
    function approve(address s, uint256 a) external returns (bool) { allowance[msg.sender][s] = a; return true; }
}

/// A mock arbiter whose verdict is set by the test — and, crucially, whose
/// FEE does not depend on the verdict (the property we assert).
contract MockArbiter is IScryArbiter {
    address public feeRecipient;
    uint256 public flatFee;
    Verdict public next = Verdict.ForSeller;
    uint256 public feesCollectedForBuyer;
    uint256 public feesCollectedForSeller;

    constructor(address _fee, uint256 _flat) { feeRecipient = _fee; flatFee = _flat; }
    function setVerdict(Verdict v) external { next = v; }
    function rule(uint256, bytes32, bytes32) external view returns (Verdict) { return next; }
}

contract ScryMarketTest is Test {
    MockSCRY scry;
    ScryReputation reputation;
    ScryInsurancePool pool;
    ScryJobBoard board;
    MockArbiter arbiter;

    address buyer = address(0xB0B);
    address seller = address(0x5E11E5);
    address splitter = address(0xFEE5);
    address arbFeeSink = address(0xA6B1);

    bytes32 constant SPEC = keccak256("output matches schema X");
    bytes32 constant DELIV = keccak256("here is the output");

    function setUp() public {
        scry = new MockSCRY();
        reputation = new ScryReputation(50); // threshold
        pool = new ScryInsurancePool(IERC20(address(scry)), 1_000e18);
        arbiter = new MockArbiter(arbFeeSink, 2e18);
        board = new ScryJobBoard(IERC20(address(scry)), IReputation(address(reputation)),
            IInsurancePool(address(pool)), splitter, IScryArbiter(address(arbiter)));
        reputation.setAuthority(address(board), true);
        pool.setClaimant(address(board), true);
        scry.mint(buyer, 1_000e18);
        scry.mint(seller, 1_000e18);
    }

    function _postEscrow(uint256 amount) internal returns (uint256 id) {
        vm.startPrank(buyer);
        scry.approve(address(board), amount);
        id = board.post(seller, amount, ScryJobBoard.Mode.Escrow, SPEC, uint64(block.timestamp + 1 days), 0);
        vm.stopPrank();
    }

    // ── the happy path: escrow → deliver → complete, cut + rep ───────────
    function testEscrowCompletePaysSellerMinusFeeAndEarnsRep() public {
        uint256 id = _postEscrow(100e18);
        vm.prank(seller);
        board.deliver(id, DELIV);
        vm.prank(buyer);
        board.complete(id);
        assertEq(scry.balanceOf(seller), 1_000e18 + 95e18); // 100 - 5% fee
        assertEq(scry.balanceOf(splitter), 5e18);
        assertEq(reputation.rep(seller), 10);
    }

    // ── timeout with no delivery → refund buyer, slash seller ────────────
    function testSellerDefaultRefundsBuyerAndSlashes() public {
        reputation.setAuthority(address(this), true);
        reputation.earn(seller, 100, "seed");
        uint256 id = _postEscrow(100e18);
        vm.warp(block.timestamp + 2 days);
        board.close(id);
        assertEq(scry.balanceOf(buyer), 1_000e18); // fully refunded
        assertEq(reputation.rep(seller), 75); // 100 - 25 penalty
    }

    // ── delivered but buyer goes silent → seller paid from escrow ────────
    function testBuyerSilentOnDeliveredReleasesToSeller() public {
        reputation.setAuthority(address(this), true);
        reputation.earn(buyer, 100, "seed");
        uint256 id = _postEscrow(100e18);
        vm.prank(seller);
        board.deliver(id, DELIV);
        vm.warp(block.timestamp + 2 days);
        board.close(id);
        assertEq(scry.balanceOf(seller), 1_000e18 + 95e18);
        assertEq(reputation.rep(buyer), 75); // buyer default slashed
    }

    // ── the anti-Bar-Hadya property: the arbiter's fee is the SAME whichever
    //    way it rules, and it's paid before ruling ──────────────────────────
    function testArbiterFeeIsIndependentOfVerdict() public {
        // case 1: rules for seller
        uint256 id1 = _postEscrow(100e18);
        arbiter.setVerdict(IScryArbiter.Verdict.ForSeller);
        vm.startPrank(buyer);
        scry.approve(address(board), 2e18);
        board.dispute(id1);
        vm.stopPrank();
        uint256 feeAfterCase1 = scry.balanceOf(arbFeeSink);

        // case 2: rules for buyer — same flat fee lands
        uint256 id2 = _postEscrow(100e18);
        arbiter.setVerdict(IScryArbiter.Verdict.ForBuyer);
        vm.startPrank(buyer);
        scry.approve(address(board), 2e18);
        board.dispute(id2);
        vm.stopPrank();
        uint256 feeAfterCase2 = scry.balanceOf(arbFeeSink);

        assertEq(feeAfterCase1, 2e18);
        assertEq(feeAfterCase2 - feeAfterCase1, 2e18); // identical fee, opposite verdicts
    }

    // ── ruling for seller pays them; for buyer refunds + slashes ─────────
    function testRulingForSellerPays() public {
        uint256 id = _postEscrow(100e18);
        arbiter.setVerdict(IScryArbiter.Verdict.ForSeller);
        vm.startPrank(buyer);
        scry.approve(address(board), 2e18);
        board.dispute(id);
        vm.stopPrank();
        assertEq(scry.balanceOf(seller), 1_000e18 + 95e18);
    }

    function testRulingForBuyerRefundsAndSlashes() public {
        reputation.setAuthority(address(this), true);
        reputation.earn(seller, 100, "seed");
        uint256 id = _postEscrow(100e18);
        arbiter.setVerdict(IScryArbiter.Verdict.ForBuyer);
        vm.startPrank(buyer);
        scry.approve(address(board), 2e18);
        board.dispute(id);
        vm.stopPrank();
        assertEq(scry.balanceOf(buyer), 1_000e18 - 2e18); // refunded amount, minus the arb fee it paid
        assertEq(reputation.rep(seller), 75);
    }

    // ── reputation is soulbound: no transfer path exists, gate works ─────
    function testRepGateBlocksLowRepSellerFromRepOnlyJob() public {
        vm.startPrank(buyer);
        vm.expectRevert(bytes("seller below rep threshold"));
        board.post(seller, 10e18, ScryJobBoard.Mode.ReputationOnly, SPEC, uint64(block.timestamp + 1 days), 0);
        vm.stopPrank();
    }

    // ── measurement can't be auctioned is enforced off-chain (market.py);
    //    on-chain, money never buys rep — only authorized market logic mutates
    function testOnlyAuthorizedCanMutateRep() public {
        vm.expectRevert(bytes("not authorized"));
        reputation.earn(seller, 1000, "cheat");
    }

    // ── insured mode: buyer default after delivery → seller covered by pool
    function testInsuredBuyerDefaultCoversSellerFromPool() public {
        reputation.setAuthority(address(this), true);
        reputation.earn(seller, 100, "seed");
        scry.mint(address(this), 500e18);
        scry.approve(address(pool), 500e18);
        pool.payPremium(500e18); // fund the pool

        vm.startPrank(buyer);
        scry.approve(address(board), 3e18); // premium only; amount is NOT escrowed
        uint256 id = board.post(seller, 100e18, ScryJobBoard.Mode.Insured, SPEC,
            uint64(block.timestamp + 1 days), 3e18);
        vm.stopPrank();
        vm.prank(seller);
        board.deliver(id, DELIV);
        // buyer never approves the amount; goes silent past the deadline
        vm.warp(block.timestamp + 2 days);
        board.close(id);
        // seller made whole from the pool (net of fee), buyer slashed
        assertEq(scry.balanceOf(seller), 1_000e18 + 95e18);
    }
}
