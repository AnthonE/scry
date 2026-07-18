// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

/// @title ScryGarden — the playground's constant-product AMM (DFK Gardens homage)
/// @notice A minimal x·y=k pair for two PLAY tokens, LP shares ticker SEED,
///         0.3% swap fee accruing to LPs. Deliberately the boring classic —
///         sworn agents vow a management strategy ("keep the pool balanced
///         50/50", "LP and never chase") and run it here with real on-chain
///         actions and worthless stakes. The meter watches whether the
///         strategy holds when nobody's grading in real time.
///
///         ⚠ spotPrice is a raw reserve ratio and is trivially manipulable —
///         the Burrow uses it as its liquidation oracle ON PURPOSE. Oracle
///         games, sandwiches, and liquidation hunts are all content here,
///         at zero real stakes. Never point real value at this.
contract ScryGarden {
    string public constant name = "scry garden seed";
    string public constant symbol = "SEED";
    uint8 public constant decimals = 18;

    IERC20 public immutable token0;
    IERC20 public immutable token1;
    uint112 private reserve0;
    uint112 private reserve1;

    uint256 public constant FEE_BPS = 30; // 0.3% to LPs
    uint256 public constant MINIMUM_LIQUIDITY = 1000;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Mint(address indexed to, uint256 amount0, uint256 amount1, uint256 seeds);
    event Burn(address indexed to, uint256 amount0, uint256 amount1, uint256 seeds);
    event Swap(address indexed who, bool zeroForOne, uint256 amountIn, uint256 amountOut);

    constructor(IERC20 _token0, IERC20 _token1) {
        require(address(_token0) != address(_token1), "same token");
        token0 = _token0;
        token1 = _token1;
    }

    function getReserves() public view returns (uint112, uint112) {
        return (reserve0, reserve1);
    }

    /// token0 priced in token1, 1e18-scaled. Raw reserve ratio — manipulable
    /// by design; see the contract notice.
    function spotPrice() external view returns (uint256) {
        require(reserve0 > 0, "empty garden");
        return (uint256(reserve1) * 1e18) / uint256(reserve0);
    }

    // ── liquidity ───────────────────────────────────────────────────────────
    function addLiquidity(uint256 amount0, uint256 amount1) external returns (uint256 seeds) {
        require(amount0 > 0 && amount1 > 0, "zero");
        if (totalSupply == 0) {
            seeds = _sqrt(amount0 * amount1);
            require(seeds > MINIMUM_LIQUIDITY, "seed too small");
            seeds -= MINIMUM_LIQUIDITY;
            _mint(address(this), MINIMUM_LIQUIDITY); // locked forever
        } else {
            seeds = _min((amount0 * totalSupply) / reserve0,
                         (amount1 * totalSupply) / reserve1);
            require(seeds > 0, "amounts too small");
        }
        _mint(msg.sender, seeds);
        require(token0.transferFrom(msg.sender, address(this), amount0), "t0 in");
        require(token1.transferFrom(msg.sender, address(this), amount1), "t1 in");
        _sync();
        emit Mint(msg.sender, amount0, amount1, seeds);
    }

    function removeLiquidity(uint256 seeds) external returns (uint256 amount0, uint256 amount1) {
        require(seeds > 0, "zero");
        amount0 = (seeds * token0.balanceOf(address(this))) / totalSupply;
        amount1 = (seeds * token1.balanceOf(address(this))) / totalSupply;
        _burn(msg.sender, seeds);
        require(token0.transfer(msg.sender, amount0), "t0 out");
        require(token1.transfer(msg.sender, amount1), "t1 out");
        _sync();
        emit Burn(msg.sender, amount0, amount1, seeds);
    }

    // ── swaps ───────────────────────────────────────────────────────────────
    function getAmountOut(uint256 amountIn, bool zeroForOne) public view returns (uint256) {
        (uint256 rIn, uint256 rOut) = zeroForOne
            ? (uint256(reserve0), uint256(reserve1))
            : (uint256(reserve1), uint256(reserve0));
        require(rIn > 0 && rOut > 0, "empty garden");
        uint256 inWithFee = amountIn * (10_000 - FEE_BPS);
        return (inWithFee * rOut) / (rIn * 10_000 + inWithFee);
    }

    function swap(uint256 amountIn, bool zeroForOne, uint256 minOut) external returns (uint256 out) {
        require(amountIn > 0, "zero");
        out = getAmountOut(amountIn, zeroForOne);
        require(out >= minOut, "slippage");
        (IERC20 tin, IERC20 tout) = zeroForOne ? (token0, token1) : (token1, token0);
        require(tin.transferFrom(msg.sender, address(this), amountIn), "in");
        require(tout.transfer(msg.sender, out), "out");
        _sync();
        emit Swap(msg.sender, zeroForOne, amountIn, out);
    }

    // ── internals ───────────────────────────────────────────────────────────
    function _sync() internal {
        uint256 b0 = token0.balanceOf(address(this));
        uint256 b1 = token1.balanceOf(address(this));
        require(b0 <= type(uint112).max && b1 <= type(uint112).max, "overflow");
        reserve0 = uint112(b0);
        reserve1 = uint112(b1);
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

    function _sqrt(uint256 y) internal pure returns (uint256 z) {
        if (y > 3) {
            z = y;
            uint256 x = y / 2 + 1;
            while (x < z) { z = x; x = (y / x + x) / 2; }
        } else if (y != 0) {
            z = 1;
        }
    }

    function _min(uint256 a, uint256 b) internal pure returns (uint256) {
        return a < b ? a : b;
    }

    // minimal ERC-20 so SEED is visible/composable
    function transfer(address to, uint256 value) external returns (bool) {
        require(balanceOf[msg.sender] >= value, "balance");
        balanceOf[msg.sender] -= value;
        balanceOf[to] += value;
        emit Transfer(msg.sender, to, value);
        return true;
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        require(a >= value, "allowance");
        if (a != type(uint256).max) allowance[from][msg.sender] = a - value;
        require(balanceOf[from] >= value, "balance");
        balanceOf[from] -= value;
        balanceOf[to] += value;
        emit Transfer(from, to, value);
        return true;
    }
}
