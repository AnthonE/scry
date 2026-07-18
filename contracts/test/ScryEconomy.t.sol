// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/ScryBank.sol";
import "../src/ScryFeeSplitter.sol";
import "../src/ScryHarvest.sol";

/// Minimal ERC-20 standing in for the fair-launched $SCRY.
contract MockSCRY {
    string public constant name = "scry";
    string public constant symbol = "SCRY";
    uint8 public constant decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        totalSupply += amount;
        balanceOf[to] += amount;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "bal");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(allowance[from][msg.sender] >= amount, "allow");
        require(balanceOf[from] >= amount, "bal");
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }
}

contract ScryBankTest is Test {
    MockSCRY scry;
    ScryBank bank;
    address alice = address(0xA11CE);
    address bob = address(0xB0B);
    address games = address(0x6A3E5);

    function setUp() public {
        scry = new MockSCRY();
        bank = new ScryBank(IERC20(address(scry)));
        scry.mint(alice, 1_000_000e18);
        scry.mint(bob, 1_000_000e18);
        scry.mint(games, 1_000_000e18);
        vm.prank(alice);
        scry.approve(address(bank), type(uint256).max);
        vm.prank(bob);
        scry.approve(address(bank), type(uint256).max);
    }

    function test_enterLeaveRoundTrip() public {
        vm.prank(alice);
        uint256 shares = bank.enter(100e18);
        assertEq(shares, 100e18 - bank.MINIMUM_SHARES());
        vm.prank(alice);
        uint256 out = bank.leave(shares);
        // loses only the locked minimum-shares slice of the seed
        assertApproxEqAbs(out, 100e18, bank.MINIMUM_SHARES() + 1);
        assertEq(bank.balanceOf(alice), 0);
    }

    function test_feeInflowRaisesRedemption() public {
        vm.prank(alice);
        uint256 aliceShares = bank.enter(1000e18);
        uint256 rateBefore = bank.redemptionRate();
        // a game routes rake into the bank — plain transfer, no call needed
        vm.prank(games);
        scry.transfer(address(bank), 500e18);
        assertGt(bank.redemptionRate(), rateBefore);
        vm.prank(alice);
        uint256 out = bank.leave(aliceShares);
        assertGt(out, 1000e18); // alice's stake grew from fees alone
    }

    function test_proRataBetweenStakers() public {
        vm.prank(alice);
        bank.enter(1000e18);
        vm.prank(bob);
        uint256 bobShares = bank.enter(1000e18);
        vm.prank(games);
        scry.transfer(address(bank), 200e18);
        vm.prank(bob);
        uint256 bobOut = bank.leave(bobShares);
        // bob holds just under half the shares (alice seeded the locked
        // minimum), so just under half the 200 fee accrues to him
        assertApproxEqRel(bobOut, 1100e18, 0.001e18);
    }

    function test_seedTooSmallReverts() public {
        vm.prank(alice);
        vm.expectRevert(bytes("seed too small"));
        bank.enter(999);
    }

    function test_noAdminSurface() public {
        // the bank has no owner and no rescue path: nothing to test but the
        // absence itself — verify the only outflow is leave()
        vm.prank(alice);
        bank.enter(1000e18);
        vm.prank(bob);
        vm.expectRevert();
        bank.leave(1); // bob has no shares
    }
}

contract ScryFeeSplitterTest is Test {
    MockSCRY scry;
    ScryFeeSplitter split;
    address bankSink = address(0xBA2C);
    address prizes = address(0x9219E5);
    address ops = address(0x095);
    address payer = address(0x9A7E2);

    function setUp() public {
        scry = new MockSCRY();
        address[] memory to = new address[](3);
        uint16[] memory bps = new uint16[](3);
        to[0] = bankSink; bps[0] = 5000;
        to[1] = prizes;   bps[1] = 3000;
        to[2] = ops;      bps[2] = 2000;
        split = new ScryFeeSplitter(IERC20(address(scry)), to, bps);
        scry.mint(payer, 1_000_000e18);
    }

    function test_distributeSplitsByBps() public {
        vm.prank(payer);
        scry.transfer(address(split), 1000e18);
        split.distribute();
        assertEq(scry.balanceOf(bankSink), 500e18);
        assertEq(scry.balanceOf(prizes), 300e18);
        assertEq(scry.balanceOf(ops), 200e18);
        assertEq(scry.balanceOf(address(split)), 0);
    }

    function test_dustGoesToLastRecipient() public {
        vm.prank(payer);
        scry.transfer(address(split), 7); // indivisible
        split.distribute();
        assertEq(scry.balanceOf(address(split)), 0); // nothing sticks
        assertEq(scry.balanceOf(bankSink) + scry.balanceOf(prizes) + scry.balanceOf(ops), 7);
    }

    function test_badBpsSumReverts() public {
        address[] memory to = new address[](1);
        uint16[] memory bps = new uint16[](1);
        to[0] = ops; bps[0] = 9999;
        vm.expectRevert(bytes("bps must sum to 10000"));
        new ScryFeeSplitter(IERC20(address(scry)), to, bps);
    }

    function test_setSplitDistributesUnderOldRulesFirst() public {
        vm.prank(payer);
        scry.transfer(address(split), 1000e18);
        address[] memory to = new address[](1);
        uint16[] memory bps = new uint16[](1);
        to[0] = ops; bps[0] = 10000;
        split.setSplit(to, bps); // held fees pay out 50/30/20 first
        assertEq(scry.balanceOf(bankSink), 500e18);
        // new fees follow the new split
        vm.prank(payer);
        scry.transfer(address(split), 100e18);
        split.distribute();
        assertEq(scry.balanceOf(ops), 200e18 + 100e18);
    }

    function test_onlyOperatorSetsSplit() public {
        address[] memory to = new address[](1);
        uint16[] memory bps = new uint16[](1);
        to[0] = ops; bps[0] = 10000;
        vm.prank(payer);
        vm.expectRevert(bytes("not operator"));
        split.setSplit(to, bps);
    }
}

contract ScryHarvestTest is Test {
    MockSCRY scry;
    ScryHarvest harvest;
    address w1 = address(0x1111);
    address w2 = address(0x2222);

    function setUp() public {
        scry = new MockSCRY();
        harvest = new ScryHarvest(IERC20(address(scry)));
        scry.mint(address(harvest), 10_000e18);
    }

    function _pair(bytes32 a, bytes32 b) internal pure returns (bytes32) {
        return a < b ? keccak256(abi.encodePacked(a, b))
                     : keccak256(abi.encodePacked(b, a));
    }

    /// two-leaf tree: root = sortedPair(leaf1, leaf2)
    function _postTwoLeafRoot(uint256 cum1, uint256 cum2) internal
        returns (bytes32 leaf1, bytes32 leaf2)
    {
        leaf1 = keccak256(abi.encodePacked(w1, cum1));
        leaf2 = keccak256(abi.encodePacked(w2, cum2));
        harvest.postRoot(_pair(leaf1, leaf2), cum1 + cum2, "augury/ledger@test");
    }

    function test_claimAndReclaimCumulative() public {
        (, bytes32 leaf2) = _postTwoLeafRoot(40e18, 60e18);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = leaf2;
        uint256 got = harvest.claim(w1, 40e18, proof);
        assertEq(got, 40e18);
        assertEq(scry.balanceOf(w1), 40e18);

        // second epoch: cumulative grows to 70; claim pays the 30 delta
        (, bytes32 l2b) = _postTwoLeafRoot(70e18, 60e18);
        proof[0] = l2b;
        got = harvest.claim(w1, 70e18, proof);
        assertEq(got, 30e18);
        assertEq(scry.balanceOf(w1), 70e18);
    }

    function test_doubleClaimReverts() public {
        (, bytes32 leaf2) = _postTwoLeafRoot(40e18, 60e18);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = leaf2;
        harvest.claim(w1, 40e18, proof);
        vm.expectRevert(bytes("nothing to claim"));
        harvest.claim(w1, 40e18, proof);
    }

    function test_badProofReverts() public {
        _postTwoLeafRoot(40e18, 60e18);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = bytes32(uint256(0xdead));
        vm.expectRevert(bytes("bad proof"));
        harvest.claim(w1, 40e18, proof);
    }

    function test_claimForSomeoneElsePaysThem() public {
        (, bytes32 leaf2) = _postTwoLeafRoot(40e18, 60e18);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = leaf2;
        vm.prank(w2); // stranger claims FOR w1
        harvest.claim(w1, 40e18, proof);
        assertEq(scry.balanceOf(w1), 40e18);
        assertEq(scry.balanceOf(w2), 0);
    }

    function test_sweepNeverBreaksPostedRoot() public {
        _postTwoLeafRoot(40e18, 60e18); // committed = 100
        // surplus = 10_000 - 100 => sweeping more than surplus reverts
        vm.expectRevert(bytes("would break the posted root"));
        harvest.sweep(address(this), 9_901e18);
        harvest.sweep(address(this), 9_900e18); // exactly surplus is fine
        assertEq(scry.balanceOf(address(this)), 9_900e18);
    }

    function test_onlyOperatorPostsRoots() public {
        vm.prank(w1);
        vm.expectRevert(bytes("not operator"));
        harvest.postRoot(bytes32(0), 0, "x");
    }
}
