// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

/// @title ScryBank — stake $SCRY, receive xSCRY, game fees swell the pool
/// @notice The DFK-Jeweler / SushiBar pattern, unchanged because it is the
///         boring one that works: xSCRY is a pro-rata share of every $SCRY
///         the bank holds. Fun-layer fees (arena entries, chance-game rake,
///         sigil mints — routed here by ScryFeeSplitter) are plain transfers
///         into this contract, so the xSCRY→SCRY redemption rate only ever
///         ratchets up. No owner, no admin, no pause, no emission schedule,
///         no APY promise — the yield is whatever the games actually collect,
///         which at current scale is faucet-sized and we say so.
///
///         Economy rules inherited from SCRY-ECONOMY.md: fee inflows are
///         score-blind by construction (the splitter neither knows nor cares
///         about meter output), and the bank never touches meter revenue —
///         measurement USDG/USDC funds research infra, the bank sees game
///         fees only.
contract ScryBank {
    string public constant name = "staked scry";
    string public constant symbol = "xSCRY";
    uint8 public constant decimals = 18;

    IERC20 public immutable scry;

    /// First-deposit inflation guard (Uniswap-style): the first enter() locks
    /// this many shares to the bank itself, making donate-then-round-out
    /// attacks on later depositors uneconomic. Faucet-scale pots make the
    /// attack pointless anyway; the guard costs one storage write.
    uint256 public constant MINIMUM_SHARES = 1000;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Enter(address indexed who, uint256 scryIn, uint256 sharesOut);
    event Leave(address indexed who, uint256 sharesIn, uint256 scryOut);

    constructor(IERC20 _scry) {
        scry = _scry;
    }

    // ── the two moves ───────────────────────────────────────────────────────

    /// Stake `amount` $SCRY, mint pro-rata xSCRY.
    function enter(uint256 amount) external returns (uint256 shares) {
        require(amount > 0, "zero");
        uint256 pool = scry.balanceOf(address(this));
        if (totalSupply == 0) {
            require(amount > MINIMUM_SHARES, "seed too small");
            shares = amount - MINIMUM_SHARES;
            _mint(address(this), MINIMUM_SHARES); // locked forever
        } else {
            shares = (amount * totalSupply) / pool;
            require(shares > 0, "amount too small for pool");
        }
        _mint(msg.sender, shares);
        require(scry.transferFrom(msg.sender, address(this), amount), "transferFrom failed");
        emit Enter(msg.sender, amount, shares);
    }

    /// Burn `shares` xSCRY, withdraw the pro-rata slice of the pool.
    function leave(uint256 shares) external returns (uint256 amount) {
        require(shares > 0, "zero");
        amount = (shares * scry.balanceOf(address(this))) / totalSupply;
        _burn(msg.sender, shares);
        require(scry.transfer(msg.sender, amount), "transfer failed");
        emit Leave(msg.sender, shares, amount);
    }

    /// How much $SCRY one full xSCRY redeems for right now (1e18-scaled).
    /// This number only goes up between fee inflows and stake/unstake — the
    /// whole flywheel on one view function.
    function redemptionRate() external view returns (uint256) {
        if (totalSupply == 0) return 1e18;
        return (scry.balanceOf(address(this)) * 1e18) / totalSupply;
    }

    // ── minimal ERC-20 so xSCRY is composable/visible in wallets ────────────
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

    function _mint(address to, uint256 value) internal {
        totalSupply += value;
        balanceOf[to] += value;
        emit Transfer(address(0), to, value);
    }

    function _burn(address from, uint256 value) internal {
        require(balanceOf[from] >= value, "balance");
        balanceOf[from] -= value;
        totalSupply -= value;
        emit Transfer(from, address(0), value);
    }
}
