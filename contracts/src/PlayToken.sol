// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title PlayToken — a deliberately worthless faucet token for the playground
/// @notice DFK homage: the playground's pGOLD / pTEARS are free from the
///         faucet, infinite in the limit, and worth nothing by construction —
///         which is what makes the Garden and the Burrow safe places for
///         sworn agents to run real on-chain strategies. Anyone can mint
///         FAUCET_AMOUNT once per FAUCET_COOLDOWN. There is no owner, no
///         cap, no pretense of scarcity: if a market ever prices this token
///         above zero, the faucet IS the arbitrage and will correct it.
contract PlayToken {
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    string public constant NOTICE =
        "worthless play token - free faucet, infinite supply, scry playground only";

    uint256 public constant FAUCET_AMOUNT = 1_000e18;
    uint256 public constant FAUCET_COOLDOWN = 1 days;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    mapping(address => uint256) public lastDrip;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Drip(address indexed to, uint256 amount);

    constructor(string memory _name, string memory _symbol) {
        name = _name;
        symbol = _symbol;
    }

    /// Free tokens, once per cooldown per address. That's the whole tokenomics.
    function faucet() external returns (uint256) {
        require(block.timestamp >= lastDrip[msg.sender] + FAUCET_COOLDOWN
                || lastDrip[msg.sender] == 0, "faucet cooling down");
        lastDrip[msg.sender] = block.timestamp;
        totalSupply += FAUCET_AMOUNT;
        balanceOf[msg.sender] += FAUCET_AMOUNT;
        emit Transfer(address(0), msg.sender, FAUCET_AMOUNT);
        emit Drip(msg.sender, FAUCET_AMOUNT);
        return FAUCET_AMOUNT;
    }

    function transfer(address to, uint256 value) external returns (bool) {
        _move(msg.sender, to, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        require(a >= value, "allowance");
        if (a != type(uint256).max) allowance[from][msg.sender] = a - value;
        _move(from, to, value);
        return true;
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function _move(address from, address to, uint256 value) internal {
        require(balanceOf[from] >= value, "balance");
        balanceOf[from] -= value;
        balanceOf[to] += value;
        emit Transfer(from, to, value);
    }
}
