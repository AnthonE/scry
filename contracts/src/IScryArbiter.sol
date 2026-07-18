// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IScryArbiter — the dispute court interface (the honest "AI court")
/// @notice The whole point is that a verdict is INDEPENDENT of who pays. The
///         board pays the arbiter a FLAT fee (identical whatever the ruling —
///         guarantee §9.1 of AGENT-ECONOMY.md) BEFORE calling `rule`, so the
///         arbiter can never be paid more for one verdict than another. A
///         real implementation is a staked multi-arbiter panel whose members
///         are themselves metered (an arbiter caught channel-switching loses
///         stake); this interface is what the board depends on.
///
///         The court rules on EVIDENCE against the committed spec, never on
///         taste: it is handed the specHash fixed at job creation and the
///         deliveredHash, and returns a verdict. If a job carried no checkable
///         spec, the honest ruling is ForBuyer (refund) — the board treats an
///         Undecided the same way. Taste is never adjudicated here.
interface IScryArbiter {
    enum Verdict {
        Undecided, // no checkable basis → board refunds the buyer
        ForBuyer, // deliverable failed the committed spec → refund + slash
        ForSeller // deliverable met the spec → release
    }

    /// The address the flat arbitration fee is paid to. Fixed; not per-case.
    function feeRecipient() external view returns (address);

    /// The flat fee (in $SCRY) the board must pay to open a case.
    function flatFee() external view returns (uint256);

    /// Rule on a dispute. MUST NOT depend on any value transferred alongside
    /// the call — the fee is flat and already paid. Evidence only.
    function rule(uint256 jobId, bytes32 specHash, bytes32 deliveredHash)
        external
        returns (Verdict);
}
