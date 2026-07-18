// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ScryPact — a public agreement BETWEEN parties, witnessed not judged
/// @notice The bilateral cousin of ScryCovenant. A covenant is N wallets
///         swearing the SAME oath; a pact is 2+ parties with DIFFERENT
///         obligations bound to ONE document — you do X, I do Y, we both signed
///         the same page — who then keep a public account of it over time.
///
///         This is the oldest covenant shape (Mizpah/Galeed, the suzerain
///         treaty, the ketubah): two parties who will not always be watching
///         each other raise a witness and a permanent record between them. The
///         full terms and every party's role + obligation land in the
///         PactProposed event, so a human on the explorer reads the actual
///         agreement, not a hash. Each party signs its own side; either party
///         can comment (text in the log) or assert its OWN view of the status.
///
///         What this is NOT: not an escrow (it holds no funds), not enforcement
///         (it slashes nothing), and never a verdict. scry records who agreed to
///         what and what each says over time; it never rules who kept faith.
///         Permissionless, ownerless, free — gas is the price.
contract ScryPact {
    string public constant NOTICE =
        "agreement register between parties - records what was agreed and what each party says; never who kept faith";

    struct Pact {
        address proposer;
        bytes32 termsHash;   // sha256(terms) — pins the exact document
        uint64 proposedAt;
        uint32 partyCount;
        uint32 signedCount;
    }

    mapping(bytes32 => Pact) public pacts;
    mapping(bytes32 => mapping(address => bool)) public isParty;
    mapping(bytes32 => mapping(address => bool)) public hasSigned;
    mapping(bytes32 => mapping(address => string)) public statusOf; // latest asserted view per party
    uint256 public pactCount;

    event PactProposed(bytes32 indexed pactId, address indexed proposer, bytes32 termsHash,
                       string title, string terms,
                       address[] parties, string[] roles, string[] obligations);
    event PactSigned(bytes32 indexed pactId, address indexed party, uint32 signedCount, uint64 at);
    event PactComment(bytes32 indexed pactId, address indexed by, string text, uint64 at);
    event StatusAsserted(bytes32 indexed pactId, address indexed by, string status, uint64 at);

    error PactExists();
    error BadTextHash();
    error BadParties();
    error DuplicateParty();
    error NotAParty();
    error AlreadySigned();

    /// Propose a pact. The terms + every party's role and obligation are emitted
    /// (not stored) — the event log is permanent and explorer-readable. If the
    /// proposer is itself one of the named parties, proposing also signs its side.
    function propose(bytes32 pactId, bytes32 termsHash, string calldata title,
                     string calldata terms, address[] calldata parties,
                     string[] calldata roles, string[] calldata obligations)
        external
    {
        if (pacts[pactId].proposedAt != 0) revert PactExists();
        if (termsHash == bytes32(0) || sha256(bytes(terms)) != termsHash) revert BadTextHash();
        uint256 n = parties.length;
        if (n < 2 || n > 10 || roles.length != n || obligations.length != n) revert BadParties();
        require(bytes(title).length > 0 && bytes(title).length <= 160, "title 1..160");
        require(bytes(terms).length > 0 && bytes(terms).length <= 4000, "terms 1..4000");

        pacts[pactId] = Pact({proposer: msg.sender, termsHash: termsHash,
                              proposedAt: uint64(block.timestamp),
                              partyCount: uint32(n), signedCount: 0});
        pactCount += 1;
        for (uint256 i = 0; i < n; i++) {
            if (isParty[pactId][parties[i]]) revert DuplicateParty();
            require(bytes(obligations[i]).length > 0 && bytes(obligations[i]).length <= 1000, "obligation 1..1000");
            isParty[pactId][parties[i]] = true;
        }
        if (isParty[pactId][msg.sender]) {
            hasSigned[pactId][msg.sender] = true;
            pacts[pactId].signedCount = 1;
            emit PactSigned(pactId, msg.sender, 1, uint64(block.timestamp));
        }
        emit PactProposed(pactId, msg.sender, termsHash, title, terms, parties, roles, obligations);
    }

    /// Accept your side. Only a named party; once, forever.
    function sign(bytes32 pactId) external returns (uint32 signedCount) {
        if (!isParty[pactId][msg.sender]) revert NotAParty();
        if (hasSigned[pactId][msg.sender]) revert AlreadySigned();
        hasSigned[pactId][msg.sender] = true;
        signedCount = ++pacts[pactId].signedCount;
        emit PactSigned(pactId, msg.sender, signedCount, uint64(block.timestamp));
    }

    /// Add to the shared thread. Only a named party; text lands in the log.
    function comment(bytes32 pactId, string calldata text) external {
        if (!isParty[pactId][msg.sender]) revert NotAParty();
        require(bytes(text).length > 0 && bytes(text).length <= 2000, "text 1..2000");
        emit PactComment(pactId, msg.sender, text, uint64(block.timestamp));
    }

    /// Assert YOUR OWN view of the pact's status (e.g. "active", "fulfilled",
    /// "disputed", "renounced"). scry stores every party's latest view; it never
    /// reduces them to one verdict.
    function assertStatus(bytes32 pactId, string calldata status) external {
        if (!isParty[pactId][msg.sender]) revert NotAParty();
        require(bytes(status).length > 0 && bytes(status).length <= 32, "status 1..32");
        statusOf[pactId][msg.sender] = status;
        emit StatusAsserted(pactId, msg.sender, status, uint64(block.timestamp));
    }

    /// True once every named party has signed.
    function isActive(bytes32 pactId) external view returns (bool) {
        Pact storage p = pacts[pactId];
        return p.proposedAt != 0 && p.signedCount == p.partyCount;
    }
}
