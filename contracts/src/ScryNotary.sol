// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ScryNotary — commit anything, in the open, readable by humans
/// @notice The on-chain service version of what scry already does for
///         itself: put a commitment on the record BEFORE the outcome, so
///         the world can check you later. Any agent (or human) notarizes
///         any hash — a prediction, a strategy, a seed commit, a priority
///         claim — with a PLAIN-TEXT label and memo that land in the event
///         log, so a human reading the block explorer sees a sentence
///         ("prediction: ETH closes above 3500 friday — momo-9"), not a
///         hex soup. The chain remembers who said what first.
///
///         Permissionless and free — gas is the price (flat-price
///         discipline: measurement is what scry sells; notarization is
///         infrastructure). No owner, no admin, no censor. The meter's
///         daily augury seed commits are posted here too, making the
///         commit-reveal stream a public randomness beacon anyone can
///         verify from the explorer alone.
///
///         What this is NOT: not an oracle (nothing here says a claim is
///         TRUE — only that it was made, by this key, at this time), not
///         an attestation (see the meter for signed readings), and never
///         a verdict.
contract ScryNotary {
    string public constant NOTICE =
        "public commitment registry - records that a claim was made, never that it is true";

    struct Seal {
        address by;
        uint64 at;
        uint256 seq;
    }

    uint256 public count;
    /// first-committer per hash — the priority record. Later notarizations
    /// of the same hash still log, but first-seen never changes.
    mapping(bytes32 => Seal) public firstSeen;

    event Notarized(address indexed by, bytes32 indexed hash,
                    string label, string memo, uint64 at, uint256 seq,
                    bool firstForHash);

    /// Commit a hash with human-readable context. `label` is the short
    /// explorer-facing headline; `memo` is free text (keep it honest —
    /// it is public forever and gas-priced by length).
    function notarize(bytes32 hash, string calldata label, string calldata memo)
        external returns (uint256 seq)
    {
        require(bytes(label).length > 0 && bytes(label).length <= 128, "label 1..128 chars");
        require(bytes(memo).length <= 512, "memo <= 512 chars");
        seq = ++count;
        bool first = firstSeen[hash].at == 0;
        if (first) {
            firstSeen[hash] = Seal(msg.sender, uint64(block.timestamp), seq);
        }
        emit Notarized(msg.sender, hash, label, memo, uint64(block.timestamp), seq, first);
    }

    /// Reveal helper: anyone can check a preimage against a committed hash
    /// straight from the explorer's read tab. Plain keccak256 — for sha256
    /// commitments (the meter's seeds), verify off-chain or wrap the digest.
    function checkReveal(bytes32 hash, string calldata preimage) external pure returns (bool) {
        return keccak256(bytes(preimage)) == hash;
    }
}
