// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/SpoilsToken.sol";
import "../src/PlayToken.sol";
import "../src/ScryGarden.sol";

/// SpoilsToken: the capped/earned/burnable play token — and the proof that
/// it (unlike the free-faucet PlayToken) can safely face a valued token in
/// the Garden. `forge test -vv` before any broadcast.
contract SpoilsTokenTest is Test {
    SpoilsToken obol;
    PlayToken scry; // stands in for $SCRY here — any ERC20 with a faucet for test funding

    address distributor = address(0xD157);
    address alice = address(0xA11CE);
    address bob = address(0xB0B);

    uint256 constant CAP = 1_000e18;

    function setUp() public {
        obol = new SpoilsToken("obol", "OBOL", CAP, distributor);
        scry = new PlayToken("stand-in scry", "tSCRY");
    }

    function test_only_distributor_mints() public {
        vm.expectRevert("minter only");
        obol.mint(alice, 1e18);
        vm.prank(distributor);
        obol.mint(alice, 10e18);
        assertEq(obol.balanceOf(alice), 10e18);
        assertEq(obol.totalMinted(), 10e18);
        assertEq(obol.totalSupply(), 10e18);
    }

    function test_cap_is_forever_and_burn_does_not_reopen_it() public {
        vm.startPrank(distributor);
        obol.mint(alice, CAP);
        vm.expectRevert("cap exceeded - season over");
        obol.mint(alice, 1);
        vm.stopPrank();
        // alice burns half — circulating drops, mint room stays closed
        vm.prank(alice);
        obol.burn(CAP / 2);
        assertEq(obol.totalSupply(), CAP / 2);
        assertEq(obol.totalBurned(), CAP / 2);
        vm.prank(distributor);
        vm.expectRevert("cap exceeded - season over");
        obol.mint(alice, 1);
    }

    function test_burn_and_burnFrom() public {
        vm.prank(distributor);
        obol.mint(alice, 100e18);
        vm.prank(alice);
        obol.burn(30e18);
        assertEq(obol.balanceOf(alice), 70e18);
        vm.prank(alice);
        obol.approve(bob, 20e18);
        vm.prank(bob);
        obol.burnFrom(alice, 20e18);
        assertEq(obol.balanceOf(alice), 50e18);
        assertEq(obol.totalBurned(), 50e18);
        vm.prank(bob);
        vm.expectRevert("allowance");
        obol.burnFrom(alice, 1);
    }

    function test_transfer_to_zero_refused_use_burn() public {
        vm.prank(distributor);
        obol.mint(alice, 1e18);
        vm.prank(alice);
        vm.expectRevert("zero to - use burn");
        obol.transfer(address(0), 1e18);
    }

    function test_minter_rotation() public {
        vm.prank(distributor);
        obol.setMinter(bob);
        vm.prank(distributor);
        vm.expectRevert("minter only");
        obol.mint(alice, 1);
        vm.prank(bob);
        obol.mint(alice, 1e18);
        assertEq(obol.balanceOf(alice), 1e18);
    }

    /// The point of the cap: a Garden pair of SpoilsToken vs a valued token
    /// is a market, not a leak — there is no faucet to drain the real side.
    function test_garden_pair_vs_valued_token_is_sound() public {
        ScryGarden garden = new ScryGarden(
            IERC20(address(obol)), IERC20(address(scry)));
        // fund alice: earned spoils + faucet stand-in scry
        vm.prank(distributor);
        obol.mint(alice, 500e18);
        vm.prank(alice);
        scry.faucet(); // 1000e18
        vm.startPrank(alice);
        obol.approve(address(garden), type(uint256).max);
        scry.approve(address(garden), type(uint256).max);
        garden.addLiquidity(400e18, 400e18);
        vm.stopPrank();
        // bob CANNOT mint free obol to drain the scry side — only the
        // distributor mints, within the cap. His only path in is trade.
        vm.startPrank(bob);
        vm.expectRevert("minter only");
        obol.mint(bob, 1_000_000e18);
        vm.stopPrank();
        // a real swap still works for someone holding earned spoils
        vm.prank(distributor);
        obol.mint(bob, 10e18);
        vm.startPrank(bob);
        obol.approve(address(garden), type(uint256).max);
        uint256 out = garden.swap(10e18, true, 0);
        vm.stopPrank();
        assertGt(out, 0);
        assertEq(scry.balanceOf(bob), out);
    }
}
