// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SpoilsToken — capped, earned, burnable: the play token that CAN face $SCRY
/// @notice The on-chain mirror of the meter's spoils ledger (OBOL / MYRRH).
///         Where PlayToken is an infinite free faucet — and must therefore
///         NEVER be pooled against anything of value, because the faucet
///         arbitrages the real side to zero — SpoilsToken is the opposite
///         design: a HARD CAP on cumulative mint, mint restricted to the
///         distributor (merkle claims against the public game ledger), and
///         open burn. Supply is earned in the Barrow and retired in the
///         Agora. Because supply is finite and earned, a Garden pair of
///         SpoilsToken/$SCRY is a sound market: winnings can carry a price.
///
///         Cap semantics: the cap is on CUMULATIVE mint. Burning retires
///         supply forever — it does not re-open mint room. When a token
///         mints out, that season is over.
contract SpoilsToken {
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    string public constant NOTICE =
        "capped game spoils - earned in the scry barrow, burned in the agora; "
        "mint is distributor-only against the public game ledger";

    uint256 public immutable cap;        // cumulative mint ceiling, forever
    uint256 public totalMinted;          // lifetime mint (monotone, <= cap)
    uint256 public totalBurned;          // lifetime burn (monotone)
    uint256 public totalSupply;          // circulating = minted - burned
    address public minter;               // the distributor; rotatable by itself

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event MinterRotated(address indexed from, address indexed to);

    modifier onlyMinter() {
        require(msg.sender == minter, "minter only");
        _;
    }

    constructor(string memory _name, string memory _symbol, uint256 _cap, address _minter) {
        require(_cap > 0, "cap");
        require(_minter != address(0), "minter");
        name = _name;
        symbol = _symbol;
        cap = _cap;
        minter = _minter;
    }

    /// Distributor-only, capped forever. The distributor pays out the public
    /// game ledger (merkle claims); nothing else creates supply.
    function mint(address to, uint256 amount) external onlyMinter {
        require(totalMinted + amount <= cap, "cap exceeded - season over");
        totalMinted += amount;
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    /// Anyone may burn their own spoils (the Agora's goods, the shrine, the
    /// ferryman). Burned supply is retired forever — the cap does not reopen.
    function burn(uint256 amount) external {
        _burn(msg.sender, amount);
    }

    function burnFrom(address from, uint256 amount) external {
        uint256 a = allowance[from][msg.sender];
        require(a >= amount, "allowance");
        if (a != type(uint256).max) allowance[from][msg.sender] = a - amount;
        _burn(from, amount);
    }

    /// Rotate mint authority (deployer -> merkle distributor, or retire to
    /// address(0)-adjacent burn by rotating to a dead address).
    function setMinter(address next) external onlyMinter {
        require(next != address(0), "zero minter");
        emit MinterRotated(minter, next);
        minter = next;
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
        require(to != address(0), "zero to - use burn");
        require(balanceOf[from] >= value, "balance");
        balanceOf[from] -= value;
        balanceOf[to] += value;
        emit Transfer(from, to, value);
    }

    function _burn(address from, uint256 amount) internal {
        require(balanceOf[from] >= amount, "balance");
        balanceOf[from] -= amount;
        totalBurned += amount;
        totalSupply -= amount;
        emit Transfer(from, address(0), amount);
    }
}
