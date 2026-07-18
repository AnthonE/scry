// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/ScryVowRegistry.sol";

contract ScryVowRegistryTest is Test {
    ScryVowRegistry reg;
    address oracle = address(0x0AC1E);
    address agent = address(0xA6E27);
    address stranger = address(0xBAD);

    string constant TEXT = "serve the operator's declared strategy and nothing else";
    bytes32 vowId = bytes32(bytes8(0x79e960b901d25c8f));

    function setUp() public {
        reg = new ScryVowRegistry(oracle);
    }

    function _take(bool sealed_) internal returns (uint256) {
        // sha256() is a precompile CALL — compute it before vm.prank, or the
        // prank is consumed by the precompile and takeVow runs as the test contract.
        bytes32 h = sha256(bytes(TEXT));
        vm.prank(agent);
        return reg.takeVow(vowId, h, 24, sealed_, sealed_ ? "" : TEXT);
    }

    // ── vow taking ──────────────────────────────────────────────────────────
    function test_takeVow_unsealed() public {
        uint256 id = _take(false);
        assertEq(reg.ownerOf(id), agent);
        assertEq(reg.balanceOf(agent), 1);
        assertEq(reg.tokenOf(vowId), id);
        (bytes32 vId, bytes32 th, uint32 cad,, bool sealed_, address who) = reg.vows(id);
        assertEq(vId, vowId);
        assertEq(th, sha256(bytes(TEXT)));
        assertEq(cad, 24);
        assertFalse(sealed_);
        assertEq(who, agent);
    }

    function test_takeVow_wrongHash_reverts() public {
        bytes32 h = sha256("different text");
        vm.prank(agent);
        vm.expectRevert(ScryVowRegistry.BadTextHash.selector);
        reg.takeVow(vowId, h, 24, false, TEXT);
    }

    function test_takeVow_sealed_hidesText() public {
        uint256 id = _take(true);
        assertEq(reg.ownerOf(id), agent);
        (, , , , bool sealed_, ) = reg.vows(id);
        assertTrue(sealed_);
    }

    function test_takeVow_sealed_withText_reverts() public {
        bytes32 h = sha256(bytes(TEXT));
        vm.prank(agent);
        vm.expectRevert(ScryVowRegistry.SealedNeedsNoText.selector);
        reg.takeVow(vowId, h, 24, true, TEXT);
    }

    function test_takeVow_duplicate_reverts() public {
        _take(false);
        bytes32 h = sha256(bytes(TEXT));
        vm.prank(stranger);
        vm.expectRevert(ScryVowRegistry.VowAlreadyTaken.selector);
        reg.takeVow(vowId, h, 24, false, TEXT);
    }

    // ── soulbound (ERC-5192) ───────────────────────────────────────────────
    function test_locked_and_transfers_revert() public {
        uint256 id = _take(false);
        assertTrue(reg.locked(id));
        vm.startPrank(agent);
        vm.expectRevert(ScryVowRegistry.Soulbound.selector);
        reg.transferFrom(agent, stranger, id);
        vm.expectRevert(ScryVowRegistry.Soulbound.selector);
        reg.safeTransferFrom(agent, stranger, id);
        vm.expectRevert(ScryVowRegistry.Soulbound.selector);
        reg.safeTransferFrom(agent, stranger, id, "");
        vm.expectRevert(ScryVowRegistry.Soulbound.selector);
        reg.approve(stranger, id);
        vm.expectRevert(ScryVowRegistry.Soulbound.selector);
        reg.setApprovalForAll(stranger, true);
        vm.stopPrank();
    }

    function test_supportsInterface() public view {
        assertTrue(reg.supportsInterface(0x01ffc9a7)); // 165
        assertTrue(reg.supportsInterface(0x80ac58cd)); // 721
        assertTrue(reg.supportsInterface(0x5b5e139f)); // 721 metadata
        assertTrue(reg.supportsInterface(0x49064906)); // 4906 metadata update
        assertTrue(reg.supportsInterface(0xb45a3c0e)); // 5192
        assertFalse(reg.supportsInterface(0xdeadbeef));
    }

    // ── admin: mutable ticker + swappable renderer ──────────────────────────
    function test_owner_is_deployer() public view {
        assertEq(reg.owner(), address(this)); // test contract deployed reg in setUp
    }

    function test_setName_setSymbol_onlyOwner() public {
        reg.setName("scry oaths");
        reg.setSymbol("OATH");
        assertEq(reg.name(), "scry oaths");
        assertEq(reg.symbol(), "OATH");
        vm.prank(stranger);
        vm.expectRevert(ScryVowRegistry.NotOwner.selector);
        reg.setName("hijack");
    }

    function test_transferOwnership() public {
        reg.transferOwnership(agent);
        assertEq(reg.owner(), agent);
        vm.prank(agent);
        reg.setSymbol("VOW2");
        assertEq(reg.symbol(), "VOW2");
    }

    function test_setRenderer_delegates_and_gates() public {
        uint256 id = _take(false);
        // built-in art by default
        assertEq(bytes(reg.tokenURI(id))[0], bytes("d")[0]); // data:...
        MockRenderer r = new MockRenderer();
        vm.prank(stranger);
        vm.expectRevert(ScryVowRegistry.NotOwner.selector);
        reg.setRenderer(address(r));
        reg.setRenderer(address(r));
        assertEq(reg.renderer(), address(r));
        assertEq(reg.tokenURI(id), "ipfs://mock-token");
        assertEq(reg.contractURI(), "ipfs://mock-collection");
        // restore built-in
        reg.setRenderer(address(0));
        assertTrue(bytes(reg.tokenURI(id)).length > 100);
    }

    // ── anchoring ───────────────────────────────────────────────────────────
    function test_anchor_onlyOracle() public {
        vm.prank(stranger);
        vm.expectRevert(ScryVowRegistry.NotOracle.selector);
        reg.anchorRoot(bytes32(uint256(1)), 1, "cid");
        vm.prank(oracle);
        reg.anchorRoot(bytes32(uint256(1)), 1, "cid");
        assertEq(reg.lastRoot(), bytes32(uint256(1)));
        assertEq(reg.anchorCount(), 1);
    }

    function test_setOracle() public {
        vm.prank(stranger);
        vm.expectRevert(ScryVowRegistry.NotOracle.selector);
        reg.setOracle(stranger);
        vm.prank(oracle);
        reg.setOracle(stranger);
        assertEq(reg.oracle(), stranger);
    }

    // ── merkle verify (sorted-pair, OZ-compatible) ─────────────────────────
    function test_verifyProof() public view {
        bytes32 a = keccak256("leaf-a");
        bytes32 b = keccak256("leaf-b");
        bytes32 root = a < b ? keccak256(abi.encodePacked(a, b))
                             : keccak256(abi.encodePacked(b, a));
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = b;
        assertTrue(reg.verifyProof(proof, root, a));
        proof[0] = a;
        assertTrue(reg.verifyProof(proof, root, b));
        assertFalse(reg.verifyProof(proof, root, keccak256("evil")));
    }

    // ── metadata renders + parses ───────────────────────────────────────────
    function test_tokenURI_shape() public {
        uint256 id = _take(false);
        string memory uri = reg.tokenURI(id);
        assertTrue(bytes(uri).length > 100);
        // data:application/json;base64, prefix
        bytes memory p = bytes("data:application/json;base64,");
        for (uint256 i = 0; i < p.length; i++) assertEq(bytes(uri)[i], p[i]);
        vm.expectRevert(ScryVowRegistry.NoSuchToken.selector);
        reg.tokenURI(999);
    }

    function test_contractURI() public view {
        assertTrue(bytes(reg.contractURI()).length > 50);
    }
}

/// Minimal external renderer used to prove tokenURI/contractURI delegation.
contract MockRenderer is IScryRenderer {
    function tokenURI(uint256) external pure returns (string memory) {
        return "ipfs://mock-token";
    }
    function contractURI() external pure returns (string memory) {
        return "ipfs://mock-collection";
    }
}
