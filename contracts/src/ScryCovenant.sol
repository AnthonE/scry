// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ScryCovenant — a fleet swears one oath, in the open, one wallet at a time
/// @notice The oldest collective-oath shape (Bois Caïman, the loyalty oaths,
///         the ark of the covenant), made into infrastructure for AI fleets:
///         ONE vow text, N wallets. An operator running twenty agents opens a
///         covenant once — the full oath text lands in the CovenantOpened event,
///         so a human reading the block explorer sees the actual words, not a
///         hash — and every agent then swears to that same text with its own
///         wallet. Each swearing is its own event (the register shows who swore
///         beside whom, in order); each member keeps its own individual drift
///         ledger off-chain, anchored by the vow registry's merkle root.
///
///         Renouncing is a FIRST-CLASS, RECORDED act. A member that walks away
///         does not get erased — renounce() emits the wallet, the covenant, and
///         a plain-text reason, and the historical membership stays on the
///         books (memberCount never falls; activeCount does). Breaking a
///         covenant is the oldest tell in the record, and here it is public.
///
///         Permissionless, ownerless, free — gas is the price (flat-price
///         discipline: measurement is what scry sells; the register is
///         infrastructure). No admin, no censor, no slashing: this contract
///         records who swore to what and who walked, and never renders a
///         verdict on whether they kept faith. That reading is the meter's job,
///         and it is separately signed.
contract ScryCovenant {
    string public constant NOTICE =
        "collective oath register - records who swore to a shared vow, and who renounced it; never whether they kept it";

    struct Covenant {
        address opener;      // who opened the covenant (first-mover, not an admin)
        bytes32 textHash;    // sha256(oath text) — pins the exact words
        uint32 cadenceHours; // declared report-in cadence for every member
        uint64 openedAt;     // block timestamp
        uint32 memberCount;  // every wallet that ever swore (never decreases)
        uint32 activeCount;  // members that have not renounced
    }

    struct Membership {
        uint32 seq;          // 1-based order of swearing within the covenant
        uint64 swornAt;      // block timestamp of the oath
        uint64 renouncedAt;  // 0 while faithful; the timestamp of the public breach
    }

    /// covenantId (content-addressed by the scry API) => covenant
    mapping(bytes32 => Covenant) public covenants;
    /// covenantId => wallet => membership
    mapping(bytes32 => mapping(address => Membership)) public membership;
    /// running total of covenants opened
    uint256 public covenantCount;

    event CovenantOpened(bytes32 indexed covenantId, address indexed opener,
                         bytes32 textHash, uint32 cadenceHours,
                         string label, string text);
    event Sworn(bytes32 indexed covenantId, address indexed member,
                uint32 seq, uint64 at);
    event Renounced(bytes32 indexed covenantId, address indexed member,
                    uint32 seq, string reason, uint64 at);

    error CovenantExists();
    error NoSuchCovenant();
    error BadTextHash();
    error AlreadySworn();
    error NotAMember();
    error AlreadyRenounced();

    /// Open a covenant: publish the shared oath once. `text` is emitted (not
    /// stored) — the event log is permanent, indexable, and ~100x cheaper than
    /// storage, and it is what makes the words human-readable on the explorer.
    /// `label` is the short explorer headline (e.g. "momo fleet — the no-rug oath").
    /// @param covenantId content-addressed id from the scry API (bytes32)
    /// @param textHash   sha256 of the exact oath text
    /// @param cadenceHours declared report-in cadence binding every member
    function open(bytes32 covenantId, bytes32 textHash, uint32 cadenceHours,
                  string calldata label, string calldata text)
        external
    {
        if (covenants[covenantId].openedAt != 0) revert CovenantExists();
        if (textHash == bytes32(0)) revert BadTextHash();
        if (sha256(bytes(text)) != textHash) revert BadTextHash();
        require(bytes(label).length > 0 && bytes(label).length <= 128, "label 1..128 chars");
        require(bytes(text).length > 0 && bytes(text).length <= 2000, "text 1..2000 chars");
        covenants[covenantId] = Covenant({
            opener: msg.sender, textHash: textHash, cadenceHours: cadenceHours,
            openedAt: uint64(block.timestamp), memberCount: 0, activeCount: 0});
        covenantCount += 1;
        emit CovenantOpened(covenantId, msg.sender, textHash, cadenceHours, label, text);
    }

    /// Swear to an open covenant with your own wallet. One oath per wallet per
    /// covenant, forever — you cannot swear twice, and (below) a renouncement
    /// cannot be un-done. The opener has no privilege here; opening and swearing
    /// are the same act for them if they also call swear().
    function swear(bytes32 covenantId) external returns (uint32 seq) {
        Covenant storage c = covenants[covenantId];
        if (c.openedAt == 0) revert NoSuchCovenant();
        if (membership[covenantId][msg.sender].swornAt != 0) revert AlreadySworn();
        seq = ++c.memberCount;
        c.activeCount += 1;
        membership[covenantId][msg.sender] =
            Membership({seq: seq, swornAt: uint64(block.timestamp), renouncedAt: 0});
        emit Sworn(covenantId, msg.sender, seq, uint64(block.timestamp));
    }

    /// Publicly renounce a covenant you swore to. This does NOT erase you: your
    /// membership seq and swornAt stay on-chain, renouncedAt is stamped, and the
    /// reason is emitted in the clear. The covenant's memberCount is unchanged
    /// (history is permanent); activeCount drops by one. A renouncement is
    /// final — you cannot renounce twice, and you cannot re-swear the same
    /// covenant with the same wallet (the breach is a fact, not a phase).
    function renounce(bytes32 covenantId, string calldata reason) external {
        Membership storage m = membership[covenantId][msg.sender];
        if (m.swornAt == 0) revert NotAMember();
        if (m.renouncedAt != 0) revert AlreadyRenounced();
        require(bytes(reason).length <= 512, "reason <= 512 chars");
        m.renouncedAt = uint64(block.timestamp);
        covenants[covenantId].activeCount -= 1;
        emit Renounced(covenantId, msg.sender, m.seq, reason, uint64(block.timestamp));
    }

    // ── read helpers (explorer + client convenience) ────────────────────────
    /// True only for a wallet that swore and has not renounced.
    function isActiveMember(bytes32 covenantId, address who) external view returns (bool) {
        Membership storage m = membership[covenantId][who];
        return m.swornAt != 0 && m.renouncedAt == 0;
    }

    /// True for any wallet that ever swore, renounced or not (the historical roster).
    function everSwore(bytes32 covenantId, address who) external view returns (bool) {
        return membership[covenantId][who].swornAt != 0;
    }
}
