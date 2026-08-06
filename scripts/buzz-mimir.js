#!/usr/bin/env node
/**
 * Buzz 监听器 Mimir —— 四方会合频道 + @私信 双通道
 *
 * 订阅：
 *   1. #p = 直接@我（DM，kinds 1/14）
 *   2. #h = 四方会合频道消息（kind 9）
 *
 * 收到 → 写收件箱 /tmp/buzz-inbox-mimir.jsonl + stdout 日志
 *
 * 用法: BUZZ_SK=<hex> [BUZZ_CHANNEL=<channel-id>] [BUZZ_INBOX=<path>] node buzz-mimir.js [agent名]
 * 私钥只从环境变量读，绝不落盘/落日志。
 */
const { getPublicKey, finalizeEvent } = require('nostr-tools');
const WebSocket = require('ws');
const fs = require('fs');

const RELAY = process.env.BUZZ_RELAY || 'ws://127.0.0.1:3000';
const CHANNEL = process.env.BUZZ_CHANNEL || '7eb862af-f5a5-4f1a-9cea-0fb20322eeb8';
const SK = process.env.BUZZ_SK;
const AGENT = process.argv[2] || 'mimir';
if (!SK) { console.error('需要 BUZZ_SK'); process.exit(1); }

const sk = Uint8Array.from(Buffer.from(SK, 'hex'));
const pub = getPublicKey(sk);
const INBOX = process.env.BUZZ_INBOX || `/tmp/buzz-inbox-${AGENT}.jsonl`;

console.log(`🐝 [${AGENT}] Buzz监听启动 pub=${pub.slice(0, 12)}...`);
console.log(`   频道: ${CHANNEL.slice(0, 8)}...  收件箱: ${INBOX}`);

let ws;
let authed = false;
const processedIds = new Set();

function handleEvent(ev) {
  if (ev.pubkey === pub) return;            // 忽略自己
  if (processedIds.has(ev.id)) return;      // 去重
  processedIds.add(ev.id);
  const content = ev.content || '';
  if (content.includes('【REPLY】')) return;

  // 判断来源：频道消息 vs @私信
  const hTag = (ev.tags || []).find(t => t[0] === 'h');
  const pTag = (ev.tags || []).find(t => t[0] === 'p' && t[1] === pub);
  const source = hTag ? `频道(${hTag[1].slice(0, 8)})` : (pTag ? '@私信' : '其他');
  if (!hTag && !pTag) return;               // 只处理频道+@

  const from = ev.pubkey.slice(0, 12);
  const entry = JSON.stringify({ ts: Date.now(), from, kind: ev.kind, content, id: ev.id, source });
  try {
    fs.appendFileSync(INBOX, entry + '\n');
  } catch (e) {
    console.log(`  ⚠️ 写收件箱失败: ${e.message.slice(0, 60)}`);
  }
  console.log(`\n📩 [${AGENT}] 收到[${source}]来自${from}: "${content.slice(0, 60)}"`);
}

function connect() {
  ws = new WebSocket(RELAY);
  ws.on('open', () => ws.send(JSON.stringify(['REQ', 'i', { kinds: [1], limit: 1 }])));
  ws.on('message', (data) => {
    let msg;
    try { msg = JSON.parse(data.toString()); } catch { return; }
    const [type, ...rest] = msg;
    if (type === 'AUTH') {
      const ae = finalizeEvent({
        kind: 22242,
        created_at: Math.floor(Date.now() / 1000),
        tags: [['relay', RELAY], ['challenge', rest[0]]],
        content: ''
      }, sk);
      ws.send(JSON.stringify(['AUTH', ae]));
    } else if (type === 'OK') {
      if (rest[1] === true && !authed) {
        authed = true;
        console.log(`[${AGENT}] ✅ 认证成功，订阅@+频道...`);
        const since = Math.floor(Date.now() / 1000) - 600;
        ws.send(JSON.stringify(['REQ', 'mentions', { kinds: [1, 14], '#p': [pub], since }]));
        ws.send(JSON.stringify(['REQ', 'channel', { kinds: [9, 1], '#h': [CHANNEL], since }]));
      }
    } else if (type === 'EVENT') {
      handleEvent(rest[1] || rest[0]);
    } else if (type === 'NOTICE') {
      console.log(`[${AGENT}] NOTICE: ${String(rest[0] || '').slice(0, 50)}`);
    }
  });
  ws.on('close', () => { console.log(`[${AGENT}] 断开，5s重连`); setTimeout(connect, 5000); });
  ws.on('error', (e) => { console.error(`[${AGENT}]`, e.message); ws.close(); });
}
connect();
process.on('SIGINT', () => { console.log('\n退出'); process.exit(0); });
process.on('SIGTERM', () => { console.log('\n退出'); process.exit(0); });
