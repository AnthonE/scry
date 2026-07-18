// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/ScrySteleEdition.sol";

contract MockSCRY {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    function mint(address to, uint256 a) external { balanceOf[to] += a; }
    function approve(address s, uint256 a) external returns (bool) { allowance[msg.sender][s] = a; return true; }
    function transferFrom(address f, address t, uint256 a) external returns (bool) {
        require(balanceOf[f] >= a, "balance");
        require(allowance[f][msg.sender] >= a, "allowance");
        allowance[f][msg.sender] -= a;
        balanceOf[f] -= a; balanceOf[t] += a;
        return true;
    }
}

contract ScrySteleEditionTest is Test {
    MockSCRY scry;
    ScrySteleEdition ed;
    address splitter = address(0xFEE);
    address alice = address(0xA11CE);
    address bob = address(0xB0B);
    uint256 price = 5e18;
    bytes32 vowId = bytes32(bytes8(hex"a1b2c3d4e5f60718"));

    function setUp() public {
        scry = new MockSCRY();
        ed = new ScrySteleEdition(IERC20(address(scry)), splitter, price, "https://scry.moreright.xyz/api");
    }

    function test_mintPullsScryToSplitter() public {
        scry.mint(alice, price);
        vm.prank(alice); scry.approve(address(ed), price);
        vm.prank(alice);
        uint256 tokenId = ed.mintEdition(vowId);
        assertEq(tokenId, 1);
        assertEq(ed.ownerOf(1), alice);
        assertEq(scry.balanceOf(splitter), price);   // $SCRY went straight to the splitter
        assertEq(scry.balanceOf(alice), 0);
        (bytes32 v, uint64 edition,) = ed.editions(1);
        assertEq(v, vowId);
        assertEq(edition, 1);
    }

    function test_mintRevertsWithoutApproval() public {
        scry.mint(alice, price);
        vm.prank(alice);
        vm.expectRevert();                            // no approval → transferFrom fails
        ed.mintEdition(vowId);
    }

    function test_editionsIncrementPerVow() public {
        scry.mint(alice, price * 3);
        vm.prank(alice); scry.approve(address(ed), price * 3);
        vm.startPrank(alice);
        ed.mintEdition(vowId);
        ed.mintEdition(vowId);
        bytes32 other = bytes32(bytes8(hex"1111111111111111"));
        ed.mintEdition(other);
        vm.stopPrank();
        assertEq(ed.editionCount(vowId), 2);
        assertEq(ed.editionCount(other), 1);
        (, uint64 e2,) = ed.editions(2);
        assertEq(e2, 2);                              // second print of vowId is edition #2
    }

    function test_editionIsTransferable() public {
        scry.mint(alice, price);
        vm.prank(alice); scry.approve(address(ed), price);
        vm.prank(alice); ed.mintEdition(vowId);
        // the whole point: unlike the soulbound vow, a print can move
        vm.prank(alice); ed.transferFrom(alice, bob, 1);
        assertEq(ed.ownerOf(1), bob);
        assertEq(ed.balanceOf(bob), 1);
        assertEq(ed.balanceOf(alice), 0);
    }

    function test_tokenURIIsOnChainJson() public {
        scry.mint(alice, price);
        vm.prank(alice); scry.approve(address(ed), price);
        vm.prank(alice); ed.mintEdition(vowId);
        string memory uri = ed.tokenURI(1);
        assertEq(_prefix(uri, 29), "data:application/json;base64,");
    }

    function test_supportsErc721() public view {
        assertTrue(ed.supportsInterface(0x80ac58cd));  // ERC-721
        assertTrue(ed.supportsInterface(0x5b5e139f));  // ERC-721 Metadata
    }

    function _prefix(string memory s, uint256 n) internal pure returns (string memory) {
        bytes memory b = bytes(s);
        bytes memory out = new bytes(n);
        for (uint256 i = 0; i < n; i++) out[i] = b[i];
        return string(out);
    }
}
