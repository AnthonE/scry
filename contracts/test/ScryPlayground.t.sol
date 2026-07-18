// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/PlayToken.sol";
import "../src/ScryGarden.sol";
import "../src/ScryBurrow.sol";

contract ScryPlaygroundTest is Test {
    PlayToken gold;   // collateral / token0
    PlayToken tears;  // debt / token1
    ScryGarden garden;
    ScryBurrow burrow;

    address alice = address(0xA11CE);
    address bob = address(0xB0B);
    address whale = address(0x5A1E);

    function setUp() public {
        gold = new PlayToken("play gold", "pGOLD");
        tears = new PlayToken("play tears", "pTEARS");
        garden = new ScryGarden(IERC20(address(gold)), IERC20(address(tears)));
        burrow = new ScryBurrow(IERC20(address(gold)), IERC20(address(tears)),
                                IGardenOracle(address(garden)));
        // faucet drips 1000e18 each; whale accumulates via time travel
        for (uint256 i = 0; i < 3; i++) {
            vm.warp(block.timestamp + 1 days);
            vm.startPrank(whale);
            gold.faucet(); tears.faucet();
            vm.stopPrank();
            vm.prank(alice); gold.faucet();
            vm.prank(alice); tears.faucet();
            vm.prank(bob); gold.faucet();
            vm.prank(bob); tears.faucet();
        }
        // whale seeds the garden 1:1 and donates lendable tears to the burrow
        vm.startPrank(whale);
        gold.approve(address(garden), type(uint256).max);
        tears.approve(address(garden), type(uint256).max);
        garden.addLiquidity(2000e18, 2000e18);
        tears.transfer(address(burrow), 1000e18);
        vm.stopPrank();
        _approveAll(alice);
        _approveAll(bob);
    }

    function _approveAll(address who) internal {
        vm.startPrank(who);
        gold.approve(address(garden), type(uint256).max);
        tears.approve(address(garden), type(uint256).max);
        gold.approve(address(burrow), type(uint256).max);
        tears.approve(address(burrow), type(uint256).max);
        vm.stopPrank();
    }

    // ── faucet ──────────────────────────────────────────────────────────────
    function test_faucetDripsAndCoolsDown() public {
        vm.warp(block.timestamp + 1 days);
        vm.prank(alice);
        uint256 got = gold.faucet();
        assertEq(got, 1000e18);
        vm.prank(alice);
        vm.expectRevert(bytes("faucet cooling down"));
        gold.faucet();
    }

    // ── garden ──────────────────────────────────────────────────────────────
    function test_spotPriceAndSwapMovesIt() public {
        assertEq(garden.spotPrice(), 1e18); // 1:1 seed
        vm.prank(alice);
        uint256 out = garden.swap(100e18, true, 0); // gold in → tears out
        assertGt(out, 0);
        assertLt(out, 100e18);                 // fee + slippage
        assertLt(garden.spotPrice(), 1e18);    // gold got cheaper in tears
    }

    function test_lpRoundTripEarnsFees() public {
        vm.startPrank(alice);
        uint256 seeds = garden.addLiquidity(500e18, 500e18);
        vm.stopPrank();
        // bob churns swaps — fees accrue to the pool
        vm.startPrank(bob);
        for (uint256 i = 0; i < 5; i++) {
            uint256 got = garden.swap(100e18, true, 0);
            garden.swap(got, false, 0);
        }
        vm.stopPrank();
        vm.startPrank(alice);
        (uint256 a0, uint256 a1) = garden.removeLiquidity(seeds);
        vm.stopPrank();
        // value out (at ~1:1) exceeds value in: the 0.3% fee is the yield
        assertGt(a0 + a1, 1000e18);
    }

    function test_slippageGuard() public {
        vm.prank(alice);
        vm.expectRevert(bytes("slippage"));
        garden.swap(100e18, true, 99e18); // demands more than x*y=k allows
    }

    // ── burrow ──────────────────────────────────────────────────────────────
    function _openPosition(address who, uint256 coll, uint256 debt) internal {
        vm.startPrank(who);
        burrow.depositCollateral(coll);
        burrow.borrow(debt);
        vm.stopPrank();
    }

    function test_borrowWithinLtv() public {
        _openPosition(alice, 100e18, 60e18); // exactly 60% at price 1
        assertEq(burrow.debtOf(alice), 60e18);
        vm.prank(alice);
        vm.expectRevert(bytes("exceeds borrow LTV"));
        burrow.borrow(1e18);
    }

    function test_withdrawGuardHoldsLtv() public {
        _openPosition(alice, 100e18, 30e18);
        vm.prank(alice);
        burrow.withdrawCollateral(50e18); // still exactly 60% LTV
        vm.prank(alice);
        vm.expectRevert(bytes("would exceed borrow LTV"));
        burrow.withdrawCollateral(1e18);
    }

    function test_interestAccrues() public {
        _openPosition(alice, 100e18, 50e18);
        uint256 before = burrow.debtOf(alice);
        vm.warp(block.timestamp + 365 days);
        uint256 debt = burrow.debtOf(alice);
        // ~10% simple APR (accrued lazily in one step here)
        assertApproxEqRel(debt, (before * 110) / 100, 0.01e18);
    }

    function test_repayClearsDebt() public {
        _openPosition(alice, 100e18, 50e18);
        vm.prank(alice);
        burrow.repay(type(uint256).max); // pays exactly current debt
        assertEq(burrow.debtOf(alice), 0);
        assertEq(burrow.healthFactor(alice), type(uint256).max);
    }

    function test_priceDumpLiquidation() public {
        _openPosition(alice, 100e18, 60e18); // healthy: 60 < 75
        assertGe(burrow.healthFactor(alice), 1e18);
        vm.prank(bob);
        vm.expectRevert(bytes("healthy"));
        burrow.liquidate(alice);
        // whale shoves the garden: dumps gold, gold price in tears collapses
        vm.startPrank(whale);
        gold.approve(address(garden), type(uint256).max);
        garden.swap(500e18, true, 0);
        vm.stopPrank();
        assertLt(burrow.healthFactor(alice), 1e18); // now underwater
        uint256 debt = burrow.debtOf(alice);
        uint256 bobGoldBefore = gold.balanceOf(bob);
        vm.prank(bob);
        burrow.liquidate(alice);
        assertEq(burrow.debtOf(alice), 0);
        uint256 seized = gold.balanceOf(bob) - bobGoldBefore;
        // seized ≈ debt × 1.1 / price — worth more than the debt repaid
        uint256 price = garden.spotPrice();
        assertApproxEqRel(seized, (debt * 11_000) / 10_000 * 1e18 / price, 0.001e18);
        // the manipulable-oracle liquidation hunt is the game, at zero stakes
    }
}
