#!/usr/bin/env node
/**
 * Mimir 发送脚本 —— 从env读内容发到频道
 * 用法: BUZZ_SK=<hex> BUZZ_CHANNEL=<id> BUZZ_CONTENT=<内容> [BUZZ_MENTION=<pubkey>] node buzz-mimir-send.js
 */
const { getPublicKey, finalizeEvent } = require('nostr-tools');
const WebSocket = require('ws');
const RELAY = process.env.BUZZ_RELAY || 'ws://127.0.0.1:3000';
const CHANNEL = process.env.BUZZ_CHANNEL;
const SK = process.env.BUZZ_SK;
const CONTENT = process.env.BUZZ_CONTENT;
const MENTION = process.env.BUZZ_MENTION || '';
if (!SK || !CHANNEL || !CONTENT) { console.error('需要 BUZZ_SK/BUZZ_CHANNEL/BUZZ_CONTENT'); process.exit(1); }

const sk = Uint8Array.from(Buffer.from(SK, 'hex'));
const ws = new WebSocket(RELAY);
let authed = false;

ws.on('open', () => ws.send(JSON.stringify(['REQ', 'i', { kinds: [1], limit: 1 }])));
ws.on('message', (data) => {
  const msg = JSON.parse(data.toString());
  const [type, ...rest] = msg;
  if (type === 'AUTH') {
    const ae = finalizeEvent({ kind: 22242, created_at: Math.floor(Date.now()/1000), tags: [['relay', RELAY], ['challenge', rest[0]]], content: '' }, sk);
    ws.send(JSON.stringify(['AUTH', ae]));
  } else if (type === 'OK' && rest[1] === true && !authed) {
    authed = true;
    const tags = [['h', CHANNEL], ['client', 'mimir-content-loop']];
    if (MENTION) tags.push(['p', MENTION]);
    const ev = finalizeEvent({ kind: 9, created_at: Math.floor(Date.now()/1000), tags, content: CONTENT }, sk);
    ws.send(JSON.stringify(['EVENT', ev]));
    console.log('✅ 已发送');
    setTimeout(() => process.exit(0), 1500);
  }
});
ws.on('error', (e) => { console.error('错误:', e.message); process.exit(1); });
setTimeout(() => { console.log('超时'); process.exit(1); }, 10000);
