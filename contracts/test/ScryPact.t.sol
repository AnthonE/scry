// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/ScryPact.sol";

contract ScryPactTest is Test {
    ScryPact p;
    bytes32 pid = keccak256("audit-for-pay-1");
    string terms = "A pays B 10 USDG on delivery of the signed audit; B delivers within 72h.";
    bytes32 th;

    address A = address(0xA);   // payer + proposer
    address B = address(0xB);   // auditor
    address C = address(0xC);   // outsider

    function setUp() public {
        p = new ScryPact();
        th = sha256(bytes(terms));
    }

    function _parties() internal view returns (address[] memory a, string[] memory r, string[] memory o) {
        a = new address[](2); a[0] = A; a[1] = B;
        r = new string[](2); r[0] = "payer"; r[1] = "auditor";
        o = new string[](2); o[0] = "pay 10 USDG on delivery"; o[1] = "deliver a signed audit within 72h";
    }

    function _propose() internal {
        (address[] memory a, string[] memory r, string[] memory o) = _parties();
        vm.warp(1000);
        vm.prank(A);
        p.propose(pid, th, "audit-for-pay", terms, a, r, o);
    }

    function test_proposeRegistersPartiesAndAutoSignsProposer() public {
        _propose();
        (address proposer, bytes32 termsHash,, uint32 partyCount, uint32 signedCount) = p.pacts(pid);
        assertEq(proposer, A);
        assertEq(termsHash, th);
        assertEq(partyCount, 2);
        assertEq(signedCount, 1);            // proposer A is a party → auto-signed
        assertTrue(p.isParty(pid, A) && p.isParty(pid, B));
        assertTrue(p.hasSigned(pid, A));
        assertFalse(p.hasSigned(pid, B));
        assertFalse(p.isActive(pid));        // B has not signed yet
    }

    function test_proposeRejectsBadTermsHash() public {
        (address[] memory a, string[] memory r, string[] memory o) = _parties();
        vm.prank(A);
        vm.expectRevert(ScryPact.BadTextHash.selector);
        p.propose(pid, keccak256("wrong"), "t", terms, a, r, o);
    }

    function test_proposeRejectsTooFewParties() public {
        address[] memory a = new address[](1); a[0] = A;
        string[] memory r = new string[](1); r[0] = "only";
        string[] memory o = new string[](1); o[0] = "do it";
        vm.prank(A);
        vm.expectRevert(ScryPact.BadParties.selector);
        p.propose(pid, th, "solo", terms, a, r, o);
    }

    function test_proposeRejectsDuplicateParty() public {
        address[] memory a = new address[](2); a[0] = A; a[1] = A;
        string[] memory r = new string[](2); r[0] = "x"; r[1] = "y";
        string[] memory o = new string[](2); o[0] = "a"; o[1] = "b";
        vm.prank(A);
        vm.expectRevert(ScryPact.DuplicateParty.selector);
        p.propose(pid, th, "dup", terms, a, r, o);
    }

    function test_secondPartySignsActivates() public {
        _propose();
        vm.prank(B);
        assertEq(p.sign(pid), 2);
        assertTrue(p.isActive(pid));
    }

    function test_outsiderCannotSignOrComment() public {
        _propose();
        vm.prank(C);
        vm.expectRevert(ScryPact.NotAParty.selector);
        p.sign(pid);
        vm.prank(C);
        vm.expectRevert(ScryPact.NotAParty.selector);
        p.comment(pid, "meddling");
    }

    function test_partyCannotSignTwice() public {
        _propose();
        vm.prank(A);
        vm.expectRevert(ScryPact.AlreadySigned.selector);
        p.sign(pid);   // A auto-signed at propose
    }

    function test_commentEmitsText() public {
        _propose();
        vm.warp(1500);
        vm.expectEmit(true, true, false, true);
        emit ScryPact.PactComment(pid, B, "audit underway, on track for 48h", 1500);
        vm.prank(B);
        p.comment(pid, "audit underway, on track for 48h");
    }

    function test_eachPartyAssertsOwnStatus() public {
        _propose();
        vm.prank(B); p.sign(pid);
        vm.prank(B); p.assertStatus(pid, "fulfilled");
        vm.prank(A); p.assertStatus(pid, "disputed");
        // both views coexist on-chain; scry never reduces them to one verdict
        assertEq(p.statusOf(pid, B), "fulfilled");
        assertEq(p.statusOf(pid, A), "disputed");
    }

    function test_proposeIsOnce() public {
        _propose();
        (address[] memory a, string[] memory r, string[] memory o) = _parties();
        vm.prank(A);
        vm.expectRevert(ScryPact.PactExists.selector);
        p.propose(pid, th, "again", terms, a, r, o);
    }
}
