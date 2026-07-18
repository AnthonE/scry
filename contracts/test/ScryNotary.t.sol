// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/ScryNotary.sol";

contract ScryNotaryTest is Test {
    ScryNotary notary;
    address momo = address(0xA6E27);
    address rival = address(0xBAD);

    function setUp() public {
        notary = new ScryNotary();
    }

    function test_notarizeRecordsFirstSeen() public {
        bytes32 h = keccak256("ETH closes above 3500 friday");
        vm.warp(1000);
        vm.prank(momo);
        uint256 seq = notary.notarize(h, "prediction: ETH > 3500 fri", "sworn by momo-9");
        (address by, uint64 at, uint256 s) = notary.firstSeen(h);
        assertEq(by, momo);
        assertEq(at, 1000);
        assertEq(s, seq);
    }

    function test_firstSeenNeverChanges() public {
        bytes32 h = keccak256("the same claim");
        vm.prank(momo);
        notary.notarize(h, "claim", "first");
        vm.warp(block.timestamp + 100);
        vm.prank(rival);
        notary.notarize(h, "claim", "late copy");
        (address by,,) = notary.firstSeen(h);
        assertEq(by, momo); // priority holds
        assertEq(notary.count(), 2); // but both notarizations are logged
    }

    function test_labelBounds() public {
        vm.expectRevert(bytes("label 1..128 chars"));
        notary.notarize(bytes32(0), "", "x");
    }

    function test_checkReveal() public view {
        bytes32 h = keccak256(bytes("the seed"));
        assertTrue(notary.checkReveal(h, "the seed"));
        assertFalse(notary.checkReveal(h, "not the seed"));
    }
}
