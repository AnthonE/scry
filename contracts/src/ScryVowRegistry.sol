// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ScryVowRegistry — soulbound vows + merkle-anchored drift ledgers
/// @notice Two jobs, one small contract, zero dependencies:
///
///   1. TAKE A VOW ON-CHAIN (agent-paid, one tx). A vow is minted as an
///      ERC-5192 soulbound ERC-721 to the caller's wallet — non-transferable
///      forever, non-burnable forever (you cannot sell your oath, and the
///      record does not go away). Unsealed vow text lives in the EVENT LOG
///      (cheap, permanent, indexable); sealed vows commit only sha256(text).
///      Metadata is fully on-chain (base64 JSON + SVG, Loot-style) so the
///      token renders in any wallet with no server and no IPFS dependency.
///
///   2. ANCHOR THE OFF-CHAIN LEDGERS (oracle-paid, one tx per period). The
///      scry meter posts a merkle root over every vow's current chain head.
///      One anchor covers every ledger in existence: after it lands, no one
///      — INCLUDING the scry operator — can rewrite any anchored history
///      without breaking a proof. This is the one thing Ed25519 + hash
///      chains cannot give (the signer could re-sign); the chain closes it.
///
/// What is deliberately NOT here: report-ins (off-chain, hash-chained,
/// covered by the anchor — putting them on-chain would tax the ritual with
/// gas), readings (interpretations are not records), and any slash/stake
/// mechanics (measuring and enforcing must never be the same party; parked
/// forever — see VOWS.md).
contract ScryVowRegistry {
    // ── ERC-721 core state (transfers are banned, so this is tiny) ──────────
    string public constant name = "scry vows";
    string public constant symbol = "VOW";

    struct Vow {
        bytes32 vowId;       // content-addressed id (matches the API's vow_id, padded)
        bytes32 textHash;    // sha256(vow text)
        uint32 cadenceHours; // declared report-in cadence
        uint64 takenAt;      // block timestamp
        bool sealed_;        // true => text never published, only the hash
        address swearer;     // the wallet bound by this vow
    }

    uint256 public nextTokenId = 1;
    mapping(uint256 => Vow) public vows;          // tokenId  => vow
    mapping(bytes32 => uint256) public tokenOf;   // vowId    => tokenId (0 = untaken)
    mapping(address => uint256) private _balance; // ERC-721 balanceOf
    mapping(uint256 => address) private _owner;   // ERC-721 ownerOf

    // ── anchor state ────────────────────────────────────────────────────────
    address public oracle;         // the scry meter's anchor wallet
    bytes32 public lastRoot;
    uint64 public lastAnchorTime;
    uint64 public anchorCount;

    // ── events ──────────────────────────────────────────────────────────────
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId); // mint only
    event Locked(uint256 tokenId);                       // ERC-5192
    event VowTaken(uint256 indexed tokenId, bytes32 indexed vowId, address indexed swearer,
                   bytes32 textHash, uint32 cadenceHours, bool sealed_, string text);
    event Anchored(bytes32 indexed root, uint64 vowCount, string leavesCid, uint64 timestamp);
    event OracleTransferred(address indexed from, address indexed to);
    event ContractURIUpdated();                          // ERC-7572

    error Soulbound();
    error VowAlreadyTaken();
    error BadTextHash();
    error SealedNeedsNoText();
    error NotOracle();
    error NoSuchToken();

    constructor(address oracle_) {
        oracle = oracle_;
        emit ContractURIUpdated();
    }

    // ── taking a vow (agent-paid, agent-called) ─────────────────────────────
    /// @param vowId    content-addressed id from the scry API (bytes32-padded)
    /// @param textHash sha256 of the exact vow text
    /// @param cadenceHours declared report-in cadence
    /// @param sealed_  true => commit hash only; text must be empty
    /// @param text     the vow text (empty when sealed). Emitted, not stored —
    ///                 the event log is permanent and ~100x cheaper than storage.
    function takeVow(bytes32 vowId, bytes32 textHash, uint32 cadenceHours,
                     bool sealed_, string calldata text)
        external returns (uint256 tokenId)
    {
        if (tokenOf[vowId] != 0) revert VowAlreadyTaken();
        if (sealed_) {
            if (bytes(text).length != 0) revert SealedNeedsNoText();
        } else {
            if (sha256(bytes(text)) != textHash) revert BadTextHash();
        }
        tokenId = nextTokenId++;
        vows[tokenId] = Vow(vowId, textHash, cadenceHours, uint64(block.timestamp),
                            sealed_, msg.sender);
        tokenOf[vowId] = tokenId;
        _balance[msg.sender] += 1;
        _owner[tokenId] = msg.sender;
        emit Transfer(address(0), msg.sender, tokenId);
        emit Locked(tokenId);
        emit VowTaken(tokenId, vowId, msg.sender, textHash, cadenceHours, sealed_, text);
    }

    // ── anchoring (oracle-paid) ─────────────────────────────────────────────
    /// @param root      merkle root over keccak256(vowId . chainHead) leaves,
    ///                  sorted-pair hashing (OpenZeppelin MerkleProof compatible)
    /// @param vowCount  number of leaves under this root
    /// @param leavesCid where the leaf-set lives (IPFS CID or API URL)
    function anchorRoot(bytes32 root, uint64 vowCount, string calldata leavesCid) external {
        if (msg.sender != oracle) revert NotOracle();
        lastRoot = root;
        lastAnchorTime = uint64(block.timestamp);
        anchorCount += 1;
        emit Anchored(root, vowCount, leavesCid, uint64(block.timestamp));
    }

    function setOracle(address newOracle) external {
        if (msg.sender != oracle) revert NotOracle();
        emit OracleTransferred(oracle, newOracle);
        oracle = newOracle;
    }

    /// @notice client-side convenience: verify a sorted-pair merkle proof.
    function verifyProof(bytes32[] calldata proof, bytes32 root, bytes32 leaf)
        external pure returns (bool)
    {
        bytes32 h = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 p = proof[i];
            h = h < p ? keccak256(abi.encodePacked(h, p))
                      : keccak256(abi.encodePacked(p, h));
        }
        return h == root;
    }

    // ── ERC-721 read surface ────────────────────────────────────────────────
    function balanceOf(address who) external view returns (uint256) { return _balance[who]; }

    function ownerOf(uint256 tokenId) public view returns (address) {
        address o = _owner[tokenId];
        if (o == address(0)) revert NoSuchToken();
        return o;
    }

    /// @notice ERC-5192: every vow is locked forever.
    function locked(uint256 tokenId) external view returns (bool) {
        ownerOf(tokenId); // revert on nonexistent
        return true;
    }

    // ── soulbound: every mutation path reverts ──────────────────────────────
    function transferFrom(address, address, uint256) external pure { revert Soulbound(); }
    function safeTransferFrom(address, address, uint256) external pure { revert Soulbound(); }
    function safeTransferFrom(address, address, uint256, bytes calldata) external pure { revert Soulbound(); }
    function approve(address, uint256) external pure { revert Soulbound(); }
    function setApprovalForAll(address, bool) external pure { revert Soulbound(); }
    function getApproved(uint256) external pure returns (address) { return address(0); }
    function isApprovedForAll(address, address) external pure returns (bool) { return false; }

    // ── ERC-165 ─────────────────────────────────────────────────────────────
    function supportsInterface(bytes4 id) external pure returns (bool) {
        return id == 0x01ffc9a7   // ERC-165
            || id == 0x80ac58cd   // ERC-721
            || id == 0x5b5e139f   // ERC-721 Metadata
            || id == 0xb45a3c0e;  // ERC-5192
    }

    // ── metadata: fully on-chain (base64 JSON + SVG). No server, no IPFS. ───
    /// @notice ERC-7572 contract-level metadata, on-chain JSON.
    function contractURI() external pure returns (string memory) {
        return string.concat(
            "data:application/json;utf8,",
            '{"name":"scry vows","description":"Soulbound vows for AI agents. '
            'An agent commits a declared purpose (ERC-5192, non-transferable, '
            'non-burnable), then reports in over time to a hash-chained public '
            'ledger anchored here by merkle root. The trajectory is the record; '
            'a missed report-in is itself signal. Readings are interpretation, '
            'never a verdict. https://scry.moreright.xyz",'
            '"external_link":"https://scry.moreright.xyz/scry-watch.html"}');
    }

    function tokenURI(uint256 tokenId) external view returns (string memory) {
        Vow memory v = vows[tokenId];
        if (v.swearer == address(0)) revert NoSuchToken();
        string memory idHex = _hex16(v.vowId);
        string memory json = string.concat(
            '{"name":"scry vow ', idHex,
            '","description":"A soulbound vow: this wallet publicly committed an AI agent to a declared purpose. ',
            v.sealed_ ? 'The text is SEALED (committed by sha256). ' : 'The text is in the VowTaken event log, forever. ',
            'Ledger + trajectory: https://scry.moreright.xyz/scry-watch.html",',
            '"image":"data:image/svg+xml;base64,', _b64(bytes(_svg(idHex, v))), '",',
            '"attributes":[',
              '{"trait_type":"vow_id","value":"', idHex, '"},',
              '{"trait_type":"text_sha256","value":"', _hex32(v.textHash), '"},',
              '{"trait_type":"cadence_hours","value":', _u(v.cadenceHours), '},',
              '{"trait_type":"sealed","value":"', v.sealed_ ? "true" : "false", '"},',
              '{"display_type":"date","trait_type":"taken_at","value":', _u(v.takenAt), '}',
            ']}');
        return string.concat("data:application/json;base64,", _b64(bytes(json)));
    }

    function _svg(string memory idHex, Vow memory v) internal pure returns (string memory) {
        return string.concat(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 350 350">',
            '<rect width="350" height="350" fill="#150e28"/>',
            '<circle cx="175" cy="140" r="66" fill="none" stroke="#f4b942" stroke-width="2"/>',
            '<circle cx="175" cy="140" r="46" fill="none" stroke="#6a4a97" stroke-width="1.5"/>',
            '<circle cx="175" cy="140" r="7" fill="#00c805"/>',
            '<text x="175" y="248" text-anchor="middle" fill="#f4efe4" font-family="monospace" font-size="16">',
            v.sealed_ ? unicode"🔒 sealed vow" : "scry vow", "</text>",
            '<text x="175" y="274" text-anchor="middle" fill="#b9b0cc" font-family="monospace" font-size="13">',
            idHex, "</text>",
            '<text x="175" y="300" text-anchor="middle" fill="#c99a34" font-family="monospace" font-size="11">',
            "every ", _u(v.cadenceHours), "h &#183; soulbound &#183; scry.moreright.xyz</text></svg>");
    }

    // ── tiny pure helpers (no deps) ─────────────────────────────────────────
    function _u(uint256 x) internal pure returns (string memory s) {
        if (x == 0) return "0";
        uint256 t = x; uint256 len;
        while (t != 0) { len++; t /= 10; }
        bytes memory b = new bytes(len);
        while (x != 0) { len--; b[len] = bytes1(uint8(48 + x % 10)); x /= 10; }
        return string(b);
    }

    function _hex32(bytes32 x) internal pure returns (string memory) {
        bytes memory a = "0123456789abcdef";
        bytes memory b = new bytes(64);
        for (uint256 i = 0; i < 32; i++) {
            b[i * 2] = a[uint8(x[i]) >> 4];
            b[i * 2 + 1] = a[uint8(x[i]) & 0x0f];
        }
        return string(b);
    }

    /// @dev first 8 bytes of a bytes32 as 16 hex chars (the API's vow_id form).
    function _hex16(bytes32 x) internal pure returns (string memory) {
        bytes memory a = "0123456789abcdef";
        bytes memory b = new bytes(16);
        for (uint256 i = 0; i < 8; i++) {
            b[i * 2] = a[uint8(x[i]) >> 4];
            b[i * 2 + 1] = a[uint8(x[i]) & 0x0f];
        }
        return string(b);
    }

    function _b64(bytes memory data) internal pure returns (string memory) {
        if (data.length == 0) return "";
        string memory table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        string memory result = new string(4 * ((data.length + 2) / 3));
        assembly {
            let tablePtr := add(table, 1)
            let resultPtr := add(result, 32)
            for { let dataPtr := data } lt(dataPtr, add(data, mload(data))) {} {
                dataPtr := add(dataPtr, 3)
                let input := mload(dataPtr)
                mstore8(resultPtr, mload(add(tablePtr, and(shr(18, input), 0x3F)))) resultPtr := add(resultPtr, 1)
                mstore8(resultPtr, mload(add(tablePtr, and(shr(12, input), 0x3F)))) resultPtr := add(resultPtr, 1)
                mstore8(resultPtr, mload(add(tablePtr, and(shr(6, input), 0x3F))))  resultPtr := add(resultPtr, 1)
                mstore8(resultPtr, mload(add(tablePtr, and(input, 0x3F))))          resultPtr := add(resultPtr, 1)
            }
            switch mod(mload(data), 3)
            case 1 { mstore8(sub(resultPtr, 1), 0x3d) mstore8(sub(resultPtr, 2), 0x3d) }
            case 2 { mstore8(sub(resultPtr, 1), 0x3d) }
        }
        return result;
    }
}
