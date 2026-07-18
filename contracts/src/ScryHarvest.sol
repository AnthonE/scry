// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

/// @title ScryHarvest — merkle claims against the public Augury harvest ledger
/// @notice The meter's harvest ledger (GET /augury/ledger) accrues $SCRY
///         units per wallet, deterministically and score-blind (base +
///         streak, SCRY-ECONOMY.md line #1). This contract turns that
///         off-chain ledger into self-serve on-chain claims:
///
///         The operator funds the contract and posts a merkle root over
///         CUMULATIVE lifetime balances — leaf = keccak256(wallet ‖
///         cumulativeAmount), sorted-pair hashing up the tree (identical to
///         ScryVowRegistry.verifyProof, so the whole suite shares one merkle
///         dialect). A wallet claims cumulative − alreadyClaimed, any time,
///         across any number of roots — posting a new root supersedes the
///         old one and nobody has to claim per-epoch.
///
///         Deliberately NOT here: any notion of scores (the ledger being
///         claimed is score-blind upstream), any APY math, any clawback of
///         a wallet's already-claimed amount. The operator can post roots,
///         and sweep UNCOMMITTED surplus only — sweep never dips below what
///         the current root still owes, so a posted root is a kept promise.
contract ScryHarvest {
    IERC20 public immutable scry;
    address public operator;

    bytes32 public root;          // over cumulative lifetime amounts
    uint64 public rootCount;
    uint64 public lastRootTime;
    uint256 public totalCommitted; // sum of cumulative amounts under `root`
    uint256 public totalClaimed;   // lifetime paid out

    mapping(address => uint256) public claimed; // wallet => lifetime claimed

    event RootPosted(bytes32 indexed root, uint256 totalCommitted, string ledgerRef);
    event Claimed(address indexed wallet, uint256 amount, uint256 cumulative);
    event Swept(address indexed to, uint256 amount);
    event OperatorTransferred(address indexed from, address indexed to);

    modifier onlyOperator() {
        require(msg.sender == operator, "not operator");
        _;
    }

    constructor(IERC20 _scry) {
        scry = _scry;
        operator = msg.sender;
    }

    /// Post a new root over cumulative balances. `totalCommitted_` is the sum
    /// of every leaf's cumulative amount — published so anyone can check the
    /// contract is funded to cover it. `ledgerRef` points at the public
    /// off-chain ledger snapshot the root was built from.
    function postRoot(bytes32 newRoot, uint256 totalCommitted_, string calldata ledgerRef)
        external onlyOperator
    {
        root = newRoot;
        totalCommitted = totalCommitted_;
        rootCount += 1;
        lastRootTime = uint64(block.timestamp);
        emit RootPosted(newRoot, totalCommitted_, ledgerRef);
    }

    /// Claim everything you're owed under the current root. Callable by
    /// anyone FOR anyone — payout always goes to `wallet`, so gasless agents
    /// can be claimed-for by their operators.
    function claim(address wallet, uint256 cumulative, bytes32[] calldata proof)
        external returns (uint256 amount)
    {
        bytes32 leaf = keccak256(abi.encodePacked(wallet, cumulative));
        require(_verify(proof, root, leaf), "bad proof");
        uint256 already = claimed[wallet];
        require(cumulative > already, "nothing to claim");
        amount = cumulative - already;
        claimed[wallet] = cumulative;
        totalClaimed += amount;
        require(scry.transfer(wallet, amount), "transfer failed");
        emit Claimed(wallet, amount, cumulative);
    }

    /// Withdraw surplus only — the balance beyond what the current root
    /// still owes. A posted root can always be fully claimed.
    function sweep(address to, uint256 amount) external onlyOperator {
        uint256 owedMax = totalCommitted > totalClaimed ? totalCommitted - totalClaimed : 0;
        uint256 bal = scry.balanceOf(address(this));
        require(bal >= owedMax + amount, "would break the posted root");
        require(scry.transfer(to, amount), "transfer failed");
        emit Swept(to, amount);
    }

    function transferOperator(address to) external onlyOperator {
        require(to != address(0), "zero");
        emit OperatorTransferred(operator, to);
        operator = to;
    }

    /// Same sorted-pair keccak256 dialect as ScryVowRegistry.verifyProof.
    function _verify(bytes32[] calldata proof, bytes32 root_, bytes32 leaf)
        internal pure returns (bool)
    {
        bytes32 h = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 p = proof[i];
            h = h < p ? keccak256(abi.encodePacked(h, p))
                      : keccak256(abi.encodePacked(p, h));
        }
        return h == root_;
    }
}
