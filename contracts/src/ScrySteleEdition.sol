// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

interface IERC721Receiver {
    function onERC721Received(address, address, uint256, bytes calldata) external returns (bytes4);
}

/// @title ScrySteleEdition — transferable prints of a vow's stele
/// @notice The vow itself is soulbound forever at ScryVowRegistry — it cannot
///         be sold, and this contract does not change that. An EDITION is a
///         separate, purely cosmetic, TRANSFERABLE print of a vow's stele that
///         anyone may mint by paying the flat $SCRY price. The $SCRY goes
///         straight to the ScryFeeSplitter (token-in / thing-out, zero chance).
///         The metadata is fully on-chain (base64 JSON + a self-contained SVG)
///         so a print renders in any wallet even if the meter is offline, and
///         links out to the live stele.
///
///         Flat price, forever (immutable at deploy). No owner, no admin, no
///         mint gate beyond payment: the print is a keepsake, not a
///         membership. Minting a print says nothing about the vow's trajectory
///         — that is the meter's signed read, never a token.
contract ScrySteleEdition {
    string public constant name = "scry stele editions";
    string public constant symbol = "STELE";

    IERC20 public immutable scry;
    address public immutable feeSplitter;
    uint256 public immutable price;      // flat $SCRY per print (18-dec units)
    string public baseURI;               // e.g. https://scry.moreright.xyz/api  (set once)

    struct Edition { bytes32 vowId; uint64 edition; uint64 mintedAt; }

    uint256 public nextTokenId = 1;
    mapping(uint256 => Edition) public editions;      // tokenId => print
    mapping(bytes32 => uint64) public editionCount;   // vowId  => prints minted
    mapping(uint256 => address) private _owner;
    mapping(address => uint256) private _balance;
    mapping(uint256 => address) private _approved;
    mapping(address => mapping(address => bool)) private _operator;

    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event Approval(address indexed owner, address indexed approved, uint256 indexed tokenId);
    event ApprovalForAll(address indexed owner, address indexed operator, bool approved);
    event EditionMinted(bytes32 indexed vowId, uint256 indexed tokenId, uint64 edition, address indexed to);

    constructor(IERC20 _scry, address _feeSplitter, uint256 _price, string memory _baseURI) {
        require(_feeSplitter != address(0), "zero splitter");
        scry = _scry;
        feeSplitter = _feeSplitter;
        price = _price;
        baseURI = _baseURI;
    }

    /// Mint a transferable print of a vow's stele. Caller must have approved
    /// this contract for `price` $SCRY; the $SCRY is pulled straight to the
    /// fee splitter. Anyone may mint any number of prints of any vow.
    function mintEdition(bytes32 vowId) external returns (uint256 tokenId) {
        require(scry.transferFrom(msg.sender, feeSplitter, price), "scry payment failed");
        uint64 ed = ++editionCount[vowId];
        tokenId = nextTokenId++;
        editions[tokenId] = Edition(vowId, ed, uint64(block.timestamp));
        _owner[tokenId] = msg.sender;
        _balance[msg.sender] += 1;
        emit Transfer(address(0), msg.sender, tokenId);
        emit EditionMinted(vowId, tokenId, ed, msg.sender);
    }

    // ── ERC-721 core (transferable, unlike the soulbound vow) ────────────────
    function ownerOf(uint256 tokenId) public view returns (address o) {
        o = _owner[tokenId];
        require(o != address(0), "no such token");
    }

    function balanceOf(address who) external view returns (uint256) {
        require(who != address(0), "zero");
        return _balance[who];
    }

    function approve(address to, uint256 tokenId) external {
        address o = ownerOf(tokenId);
        require(msg.sender == o || _operator[o][msg.sender], "not authorized");
        _approved[tokenId] = to;
        emit Approval(o, to, tokenId);
    }

    function getApproved(uint256 tokenId) external view returns (address) {
        ownerOf(tokenId);
        return _approved[tokenId];
    }

    function setApprovalForAll(address op, bool ok) external {
        _operator[msg.sender][op] = ok;
        emit ApprovalForAll(msg.sender, op, ok);
    }

    function isApprovedForAll(address o, address op) external view returns (bool) {
        return _operator[o][op];
    }

    function transferFrom(address from, address to, uint256 tokenId) public {
        require(to != address(0), "zero to");
        address o = ownerOf(tokenId);
        require(o == from, "from != owner");
        require(msg.sender == o || _approved[tokenId] == msg.sender || _operator[o][msg.sender],
                "not authorized");
        _approved[tokenId] = address(0);
        _owner[tokenId] = to;
        _balance[from] -= 1;
        _balance[to] += 1;
        emit Transfer(from, to, tokenId);
    }

    function safeTransferFrom(address from, address to, uint256 tokenId) external {
        safeTransferFrom(from, to, tokenId, "");
    }

    function safeTransferFrom(address from, address to, uint256 tokenId, bytes memory data) public {
        transferFrom(from, to, tokenId);
        if (to.code.length > 0) {
            require(IERC721Receiver(to).onERC721Received(msg.sender, from, tokenId, data)
                    == IERC721Receiver.onERC721Received.selector, "unsafe recipient");
        }
    }

    function supportsInterface(bytes4 id) external pure returns (bool) {
        return id == 0x01ffc9a7   // ERC-165
            || id == 0x80ac58cd   // ERC-721
            || id == 0x5b5e139f;  // ERC-721 Metadata
    }

    // ── metadata: fully on-chain, self-contained, links to the live stele ────
    function tokenURI(uint256 tokenId) external view returns (string memory) {
        Edition memory e = editions[tokenId];
        require(e.mintedAt != 0, "no such token");
        string memory idHex = _hex16(e.vowId);
        string memory json = string.concat(
            '{"name":"scry stele edition ', idHex, ' #', _u(e.edition),
            '","description":"A transferable print of a scry vow stele. The vow itself is soulbound '
            'forever at ScryVowRegistry and is NOT transferred by this print. Minting a print says '
            'nothing about the vow trajectory — that is the meter s signed read, never a token. '
            'Live stele: ', baseURI, '/vow/', idHex, '/stele.svg",',
            '"external_url":"', baseURI, '/vow/', idHex, '/stele.svg",',
            '"image":"data:image/svg+xml;base64,', _b64(bytes(_svg(idHex, e))), '",',
            '"attributes":[',
              '{"trait_type":"vow_id","value":"', idHex, '"},',
              '{"trait_type":"edition","value":', _u(e.edition), '},',
              '{"display_type":"date","trait_type":"minted_at","value":', _u(e.mintedAt), '}',
            ']}');
        return string.concat("data:application/json;base64,", _b64(bytes(json)));
    }

    function _svg(string memory idHex, Edition memory e) internal pure returns (string memory) {
        return string.concat(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 350 350">',
            '<rect width="350" height="350" fill="#150e28"/>',
            '<rect x="18" y="18" width="314" height="314" fill="none" stroke="#f4b942" stroke-width="1.5"/>',
            '<circle cx="175" cy="132" r="58" fill="none" stroke="#f4b942" stroke-width="2"/>',
            '<circle cx="175" cy="132" r="40" fill="none" stroke="#6a4a97" stroke-width="1.5"/>',
            '<circle cx="175" cy="132" r="6" fill="#00c805"/>',
            '<text x="175" y="228" text-anchor="middle" fill="#f4efe4" font-family="monospace" font-size="15">stele edition</text>',
            '<text x="175" y="254" text-anchor="middle" fill="#c99a34" font-family="monospace" font-size="13">edition #', _u(e.edition), '</text>',
            '<text x="175" y="280" text-anchor="middle" fill="#b9b0cc" font-family="monospace" font-size="12">', idHex, '</text>',
            '<text x="175" y="306" text-anchor="middle" fill="#6a5f85" font-family="monospace" font-size="10">a print &#183; the vow stays soulbound &#183; scry.moreright.xyz</text>',
            '</svg>');
    }

    // ── tiny pure helpers (no deps) ──────────────────────────────────────────
    function _u(uint256 x) internal pure returns (string memory s) {
        if (x == 0) return "0";
        uint256 t = x; uint256 len;
        while (t != 0) { len++; t /= 10; }
        bytes memory b = new bytes(len);
        while (x != 0) { len--; b[len] = bytes1(uint8(48 + x % 10)); x /= 10; }
        return string(b);
    }

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
