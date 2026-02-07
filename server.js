/* Minimal MCP-style JSON-RPC server for TRON data.
 *
 * Endpoints exposed via MCP tools:
 * - get_usdt_balance  : TRONSCAN account lookup and USDT TRC20 balance extraction
 * - get_network_params: TRONGRID chain parameters (energy/bandwidth fees, etc.)
 * - get_tx_status     : TRONGRID transaction confirmation and receipt summary
 * - get_token_balance : TRX/TRC20 balance by symbol/contract
 * - get_total_value   : portfolio total value in USD/CNY (CoinGecko)
 *
 * Run:  npm start  (or: node server.js)
 * RPC:  POST JSON-RPC 2.0 requests to http://localhost:8787/
 * Health: GET /health
 *
 * Notes:
 * - Requires outbound internet access to TRONSCAN/TRONGRID.
 * - Optional env vars: PORT, TRONSCAN_BASE, TRONGRID_BASE, TRONGRID_API_KEY,
 *   TRON_USDT_CONTRACT, COINGECKO_BASE, REQUEST_TIMEOUT_MS.
 */

const http = require("http");

const PORT = Number(process.env.PORT || 8787);
const TRONSCAN_BASE =
  process.env.TRONSCAN_BASE || "https://apilist.tronscanapi.com/api";
const TRONGRID_BASE =
  process.env.TRONGRID_BASE || "https://api.trongrid.io";
const TRONGRID_API_KEY =
  process.env.TRONGRID_API_KEY || process.env.TRON_PRO_API_KEY || "";
const USDT_CONTRACT =
  process.env.TRON_USDT_CONTRACT ||
  "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"; // Official TRON USDT (TRC20)
const COINGECKO_BASE =
  process.env.COINGECKO_BASE || "https://api.coingecko.com/api/v3";
const REQUEST_TIMEOUT_MS = Number(process.env.REQUEST_TIMEOUT_MS || 12000);

const serverInfo = { name: "trident-mcp-node", version: "0.2.0" };

const toolDefinitions = [
  {
    name: "get_usdt_balance",
    description:
      "Query TRONSCAN for an address and return the USDT TRC20 balance in human-readable form.",
    inputSchema: {
      type: "object",
      properties: {
        address: { type: "string", description: "TRON base58 address (starts with T)" }
      },
      required: ["address"]
    }
  },
  {
    name: "get_network_params",
    description:
      "Fetch current TRON network chain parameters (energy fee, bandwidth fee, account creation cost, etc.) via TRONGRID.",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "get_tx_status",
    description:
      "Check confirmation and receipt details for a transaction hash (txID) using TRONGRID.",
    inputSchema: {
      type: "object",
      properties: {
        txid: { type: "string", description: "Transaction hash (hex, 64 chars)" }
      },
      required: ["txid"]
    }
  },
  {
    name: "get_token_balance",
    description:
      "Fetch TRX/TRC20 balance by symbol or contract (TRONSCAN).",
    inputSchema: {
      type: "object",
      properties: {
        address: { type: "string", description: "TRON base58 address (starts with T)" },
        token: { type: "string", description: "Token symbol (e.g. USDT/TRX) or TRC20 contract address" }
      },
      required: ["address", "token"]
    }
  },
  {
    name: "get_total_value",
    description:
      "Calculate total value for all tokens (TRX + TRC20) in USD/CNY.",
    inputSchema: {
      type: "object",
      properties: {
        address: { type: "string", description: "TRON base58 address (starts with T)" },
        currency: { type: "string", description: "Fiat unit: usd or cny", enum: ["usd", "cny"] }
      },
      required: ["address"]
    }
  }
];

// --- Utility helpers -------------------------------------------------------

function isLikelyBase58Address(addr = "") {
  return /^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(addr);
}

function formatTokenAmount(rawStr, decimals = 6) {
  try {
    const raw = BigInt(rawStr);
    const divisor = BigInt(10) ** BigInt(decimals);
    const integer = raw / divisor;
    const fraction = raw % divisor;
    if (fraction === 0n) return integer.toString();
    const fractionStr = fraction.toString().padStart(decimals, "0").replace(/0+$/, "");
    return `${integer}.${fractionStr}`;
  } catch {
    return "0";
  }
}

function getTrc20Candidates(account = {}) {
  return (
    account.trc20token_balances ||
    account.trc20token_balancesV2 ||
    account.trc20 ||
    account.tokenBalances ||
    []
  );
}

function tokenContract(token = {}) {
  return (
    token.tokenId ||
    token.contract_address ||
    token.tokenAddress ||
    token.token_id ||
    token.tokenIdAddress ||
    token.address ||
    null
  );
}

function tokenSymbol(token = {}) {
  return (
    token.tokenAbbr ||
    token.symbol ||
    token.tokenSymbol ||
    token.tokenName ||
    token.name ||
    null
  );
}

function tokenDecimals(token = {}, fallback = 6) {
  return Number(token.tokenDecimal || token.decimals || token.tokenDecimals || fallback);
}

function tokenBalanceRaw(token = {}) {
  const keys = ["balance", "amount", "tokenBalance", "quantity"];
  for (const key of keys) {
    const candidate = token[key];
    if (candidate !== undefined && candidate !== null && candidate !== "" && candidate !== "0") {
      return candidate.toString();
    }
  }
  return "0";
}

function cleanContracts(contracts = []) {
  const out = [];
  const seen = new Set();
  contracts.forEach((contract) => {
    if (!contract) return;
    const value = contract.toString().trim();
    if (!value || value.includes(",") || value.includes(" ")) return;
    if (!/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(value)) return;
    if (seen.has(value)) return;
    seen.add(value);
    out.push(value);
  });
  return out;
}

async function fetchJson(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const headers = Object.assign(
    { Accept: "application/json" },
    options.headers || {}
  );

  // Attach TRON-PRO-API-KEY automatically when calling TRONGRID.
  if (!headers["TRON-PRO-API-KEY"] && TRONGRID_API_KEY && url.includes(TRONGRID_BASE)) {
    headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY;
  }

  const opts = Object.assign({}, options, { headers, signal: controller.signal });

  try {
    const res = await fetch(url, opts);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} ${res.statusText}`);
    }
    const data = await res.json();
    return data;
  } finally {
    clearTimeout(timer);
  }
}

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8"
  });
  res.end(JSON.stringify(payload));
}

function rpcResult(id, result) {
  return { jsonrpc: "2.0", id, result };
}

function rpcError(id, code, message, data) {
  const err = { jsonrpc: "2.0", id, error: { code, message } };
  if (data !== undefined) err.error.data = data;
  return err;
}

// --- Tool implementations ---------------------------------------------------

async function toolGetUsdtBalance({ address }) {
  if (!isLikelyBase58Address(address)) {
    throw new Error("Invalid TRON address format");
  }
  const url = `${TRONSCAN_BASE}/account?address=${encodeURIComponent(address)}`;
  const account = await fetchJson(url);

  const candidates =
    account.trc20token_balances ||
    account.trc20token_balancesV2 ||
    account.trc20 ||
    account.tokenBalances ||
    [];

  const usdt = candidates.find((t) => {
    const contract =
      t.tokenId ||
      t.contract_address ||
      t.tokenAddress ||
      t.token_id ||
      t.tokenIdAddress;
    return contract && contract.toUpperCase() === USDT_CONTRACT.toUpperCase();
  });

  const balanceRaw =
    (usdt && (usdt.balance || usdt.amount || usdt.tokenBalance || usdt.quantity)) ||
    "0";
  const decimals = Number(
    (usdt && (usdt.tokenDecimal || usdt.decimals)) || 6
  );

  return {
    address,
    contract: USDT_CONTRACT,
    balance: {
      raw: balanceRaw.toString(),
      human: formatTokenAmount(balanceRaw, decimals),
      decimals
    },
    source: "TRONSCAN",
    apiUrl: url,
    updated: account.updateTime || account.date_updated || null
  };
}

async function toolGetNetworkParams() {
  const url = `${TRONGRID_BASE}/wallet/getchainparameters`;
  const params = await fetchJson(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{}"
  });

  const table = new Map();
  (params.chainParameter || []).forEach((p) => {
    if (p && p.key) table.set(p.key, p.value);
  });

  const energyFeeSun = Number(table.get("getEnergyFee"));
  const bandwidthFeeSun = Number(table.get("getTransactionFee"));
  const createAccountFeeSun = Number(table.get("getCreateAccountFee"));
  const memoFeePerByteSun = Number(table.get("getMemoFee"));

  return {
    energyFeeSun,
    bandwidthFeeSun,
    createAccountFeeSun,
    memoFeePerByteSun,
    notes: "Values are in sun (1 TRX = 1,000,000 sun).",
    raw: params
  };
}

async function toolGetTxStatus({ txid }) {
  if (!txid || !/^[0-9a-fA-F]{64}$/.test(txid)) {
    throw new Error("txid must be a 64-char hex string");
  }

  const metaUrl = `${TRONGRID_BASE}/wallet/gettransactionbyid`;
  const infoUrl = `${TRONGRID_BASE}/wallet/gettransactioninfobyid`;

  const [meta, receipt] = await Promise.all([
    fetchJson(metaUrl, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ value: txid })
    }).catch(() => null),
    fetchJson(infoUrl, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ value: txid })
    }).catch(() => null)
  ]);

  let status = "NOT_FOUND";
  if (receipt && receipt.id) {
    const result = receipt.receipt?.result || receipt.result;
    if (result === "SUCCESS") status = "CONFIRMED_SUCCESS";
    else if (result) status = `CONFIRMED_${result}`;
    else status = "CONFIRMED";
  } else if (meta && meta.txID) {
    status = "PENDING_OR_UNCONFIRMED";
  }

  return {
    txid,
    status,
    blockNumber: receipt && receipt.blockNumber,
    blockTime: receipt && receipt.blockTimeStamp,
    feeSun: receipt?.fee,
    energyUsage: receipt?.receipt?.energy_usage_total,
    rawMeta: meta,
    rawReceipt: receipt
  };
}

async function fetchTokenPrices(contracts = [], currency = "usd") {
  if (!contracts.length) return {};
  const contractParam = encodeURIComponent(contracts.join(","));
  const url = `${COINGECKO_BASE}/simple/token_price/tron?contract_addresses=${contractParam}&vs_currencies=${currency}`;
  return fetchJson(url);
}

async function fetchTrxPrice(currency = "usd") {
  const url = `${COINGECKO_BASE}/simple/price?ids=tron&vs_currencies=${currency}`;
  return fetchJson(url);
}

async function toolGetTokenBalance({ address, token }) {
  if (!isLikelyBase58Address(address)) {
    throw new Error("Invalid TRON address format");
  }
  if (!token) {
    throw new Error("token is required");
  }

  const tokenKey = token.toString().trim();
  const tokenUpper = tokenKey.toUpperCase();
  const url = `${TRONSCAN_BASE}/account?address=${encodeURIComponent(address)}`;
  const account = await fetchJson(url);

  if (tokenUpper === "TRX" || tokenUpper === "TRON") {
    const balanceRaw = (account.balance || account.balanceInSun || 0).toString();
    const decimals = 6;
    return {
      address,
      token: { symbol: "TRX", contract: null, decimals, name: "TRON", matchedBy: "native" },
      balance: { raw: balanceRaw, human: formatTokenAmount(balanceRaw, decimals), decimals },
      source: "TRONSCAN",
      apiUrl: url,
      updated: account.updateTime || account.date_updated || null
    };
  }

  const candidates = getTrc20Candidates(account);
  let matched = null;
  let matchedBy = null;
  for (const item of candidates) {
    const contract = tokenContract(item);
    const symbol = tokenSymbol(item);
    if (contract && contract.toUpperCase() === tokenUpper) {
      matched = item;
      matchedBy = "contract";
      break;
    }
    if (symbol && symbol.toUpperCase() === tokenUpper) {
      matched = item;
      matchedBy = "symbol";
      break;
    }
  }

  if (!matched) {
    throw new Error(`Token not found for address: ${tokenKey}`);
  }

  const contract = tokenContract(matched);
  const symbol = tokenSymbol(matched);
  const decimals = tokenDecimals(matched);
  const balanceRaw = tokenBalanceRaw(matched);

  return {
    address,
    token: {
      symbol: symbol || tokenUpper,
      contract,
      decimals,
      name: matched.tokenName || matched.name || null,
      matchedBy
    },
    balance: {
      raw: balanceRaw,
      human: formatTokenAmount(balanceRaw, decimals),
      decimals
    },
    source: "TRONSCAN",
    apiUrl: url,
    updated: account.updateTime || account.date_updated || null
  };
}

async function toolGetTotalValue({ address, currency = "usd" }) {
  if (!isLikelyBase58Address(address)) {
    throw new Error("Invalid TRON address format");
  }
  const fiat = (currency || "usd").toLowerCase();
  if (fiat !== "usd" && fiat !== "cny") {
    throw new Error("currency must be 'usd' or 'cny'");
  }

  const url = `${TRONSCAN_BASE}/account?address=${encodeURIComponent(address)}`;
  const account = await fetchJson(url);
  const items = [];

  const trxRaw = (account.balance || account.balanceInSun || 0).toString();
  const trxDecimals = 6;
  items.push({
    token: { symbol: "TRX", contract: null, decimals: trxDecimals, name: "TRON" },
    balance: { raw: trxRaw, human: formatTokenAmount(trxRaw, trxDecimals), decimals: trxDecimals }
  });

  for (const item of getTrc20Candidates(account)) {
    const contract = tokenContract(item);
    const symbol = tokenSymbol(item);
    const decimals = tokenDecimals(item);
    const balanceRaw = tokenBalanceRaw(item);
    items.push({
      token: { symbol, contract, decimals, name: item.tokenName || item.name || null },
      balance: { raw: balanceRaw, human: formatTokenAmount(balanceRaw, decimals), decimals }
    });
  }

  const contracts = cleanContracts(items.map((i) => i.token.contract).filter(Boolean));
  const priceMap = {};
  const pricingErrors = [];
  const chunkSize = 80;
  for (let i = 0; i < contracts.length; i += chunkSize) {
    const chunk = contracts.slice(i, i + chunkSize);
    try {
      const priceMapRaw = await fetchTokenPrices(chunk, fiat);
      Object.entries(priceMapRaw || {}).forEach(([key, value]) => {
        priceMap[key.toLowerCase()] = value;
      });
    } catch (err) {
      pricingErrors.push(`CoinGecko chunk ${Math.floor(i / chunkSize) + 1}: ${err.message}`);
    }
  }
  let trxPrice = null;
  try {
    const trxPriceRaw = await fetchTrxPrice(fiat);
    trxPrice = trxPriceRaw?.tron ? trxPriceRaw.tron[fiat] : null;
  } catch (err) {
    pricingErrors.push(`CoinGecko TRX price: ${err.message}`);
  }

  let totalValue = 0;
  const missingPrices = [];
  items.forEach((item) => {
    const contract = item.token.contract;
    const symbol = item.token.symbol || contract || "UNKNOWN";
    const price = contract ? priceMap[String(contract).toLowerCase()]?.[fiat] : trxPrice;
    const amount = Number(item.balance.human);
    if (!Number.isFinite(amount) || price === undefined || price === null) {
      item.price = price ?? null;
      item.value = null;
      missingPrices.push(String(symbol));
      return;
    }
    const value = amount * Number(price);
    item.price = Number(price);
    item.value = value.toString();
    totalValue += value;
  });

  return {
    address,
    currency: fiat,
    totalValue: totalValue.toString(),
    items,
    missingPrices,
    pricingErrors,
    pricingSource: "COINGECKO",
    apiUrl: { account: url, prices: COINGECKO_BASE },
    updated: account.updateTime || account.date_updated || null
  };
}

async function dispatchTool(name, args = {}) {
  switch (name) {
    case "get_usdt_balance":
      return toolGetUsdtBalance(args);
    case "get_network_params":
      return toolGetNetworkParams();
    case "get_tx_status":
      return toolGetTxStatus(args);
    case "get_token_balance":
      return toolGetTokenBalance(args);
    case "get_total_value":
      return toolGetTotalValue(args);
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

// --- HTTP & JSON-RPC handling ----------------------------------------------

function parseJsonBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      try {
        resolve(JSON.parse(raw));
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

async function handleRpc(body, res) {
  const { id = null, method, params = {} } = body || {};

  if (!method) {
    return sendJson(res, 400, rpcError(id, -32600, "Invalid Request: missing method"));
  }

  try {
    switch (method) {
      case "initialize":
        return sendJson(
          res,
          200,
          rpcResult(id, {
            protocolVersion: "2024-11-05",
            capabilities: { tools: {} },
            serverInfo
          })
        );
      case "ping":
        return sendJson(res, 200, rpcResult(id, { pong: Date.now() }));
      case "list_tools":
        return sendJson(res, 200, rpcResult(id, { tools: toolDefinitions }));
      case "call_tool": {
        const { name, arguments: toolArgs } = params;
        if (!name) {
          return sendJson(res, 400, rpcError(id, -32602, "call_tool requires 'name'"));
        }
        const result = await dispatchTool(name, toolArgs || {});
        return sendJson(res, 200, rpcResult(id, result));
      }
      default:
        return sendJson(res, 404, rpcError(id, -32601, `Method not found: ${method}`));
    }
  } catch (err) {
    return sendJson(
      res,
      500,
      rpcError(id, -32000, err.message || "Internal error")
    );
  }
}

const server = http.createServer(async (req, res) => {
  const { method, url } = req;

  if (method === "GET" && url === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true, serverInfo }));
    return;
  }

  if (method !== "POST") {
    sendJson(res, 405, {
      error: "Only POST supported for JSON-RPC. Try POST / with jsonrpc payload."
    });
    return;
  }

  try {
    const body = await parseJsonBody(req);
    await handleRpc(body, res);
  } catch (err) {
    sendJson(res, 400, rpcError(null, -32700, `Parse error: ${err.message}`));
  }
});

server.listen(PORT, () => {
  console.log(
    `TRON MCP server listening on http://localhost:${PORT} (tools: ${toolDefinitions
      .map((t) => t.name)
      .join(", ")})`
  );
});
