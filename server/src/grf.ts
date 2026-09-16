// Reads individual entries straight out of the client's data.grf (GRF 0x200)
// using the index produced by tools/build_grf_index.py. Handles the two
// encryption modes official clients use (flag 2 mixcrypt, flag 4 "DES" — which
// despite the name only covers the first 20 blocks) and zlib inflation.
import { closeSync, openSync, readSync } from "node:fs";
import { inflateSync } from "node:zlib";

const HEADER = 46;

export type GrfIndex = Record<string, [offset: number, comp: number, aligned: number, real: number, flags: number]>;

export class GrfReader {
  private fd: number;
  private cache = new Map<string, Uint8Array>();
  private cacheBytes = 0;
  constructor(path: string, private index: GrfIndex, private maxCacheBytes = 256 * 1024 * 1024) {
    this.fd = openSync(path, "r");
  }

  has(name: string) {
    return name.toLowerCase() in this.index;
  }

  /** All index keys starting with `prefix` (lower-cased). */
  list(prefix: string) {
    const p = prefix.toLowerCase();
    return Object.keys(this.index).filter((k) => k.startsWith(p));
  }

  read(name: string): Uint8Array | null {
    const key = name.toLowerCase();
    const cached = this.cache.get(key);
    if (cached) return cached;
    const e = this.index[key];
    if (!e) return null;
    const [offset, comp, aligned, real, flags] = e;
    const buf = Buffer.alloc(aligned);
    readSync(this.fd, buf, 0, aligned, HEADER + offset);
    let data: Uint8Array = buf;
    if (flags & 4) data = desDecryptFirstBlocks(data);
    else if (flags & 2) data = desDecryptMixed(data, comp);
    data = data.subarray(0, comp);
    let out: Uint8Array;
    if (comp === real && !(data[0] === 0x78 && (data[1] === 0x9c || data[1] === 0x01 || data[1] === 0xda))) {
      out = data; // stored uncompressed
    } else {
      out = inflateSync(data);
    }
    this.cache.set(key, out);
    this.cacheBytes += out.byteLength;
    if (this.cacheBytes > this.maxCacheBytes) {
      // drop oldest half
      for (const k of [...this.cache.keys()].slice(0, this.cache.size / 2)) {
        this.cacheBytes -= this.cache.get(k)!.byteLength;
        this.cache.delete(k);
      }
    }
    return out;
  }

  close() {
    closeSync(this.fd);
  }
}

// ------------------------------------------------------------ GRF DES ------
// Single-round DES with an all-zero key, as used by Gravity's GRF format.
const IP = [58,50,42,34,26,18,10,2,60,52,44,36,28,20,12,4,62,54,46,38,30,22,14,6,64,56,48,40,32,24,16,8,
  57,49,41,33,25,17,9,1,59,51,43,35,27,19,11,3,61,53,45,37,29,21,13,5,63,55,47,39,31,23,15,7];
const FP = [40,8,48,16,56,24,64,32,39,7,47,15,55,23,63,31,38,6,46,14,54,22,62,30,37,5,45,13,53,21,61,29,
  36,4,44,12,52,20,60,28,35,3,43,11,51,19,59,27,34,2,42,10,50,18,58,26,33,1,41,9,49,17,57,25];
const E = [32,1,2,3,4,5,4,5,6,7,8,9,8,9,10,11,12,13,12,13,14,15,16,17,16,17,18,19,20,21,20,21,22,23,24,25,
  24,25,26,27,28,29,28,29,30,31,32,1];
const P = [16,7,20,21,29,12,28,17,1,15,23,26,5,18,31,10,2,8,24,14,32,27,3,9,19,13,30,6,22,11,4,25];
const S = [
  [14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7,0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8,4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0,15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13],
  [15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10,3,13,4,7,15,2,8,14,12,0,1,10,6,9,11,5,0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15,13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9],
  [10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8,13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1,13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7,1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12],
  [7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15,13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9,10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4,3,15,0,6,10,1,13,8,9,4,5,11,12,7,2,14],
  [2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9,14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6,4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14,11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3],
  [12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11,10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8,9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6,4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13],
  [4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1,13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6,1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2,6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12],
  [13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7,1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2,7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8,2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11],
];

const bits = new Uint8Array(64), tmp = new Uint8Array(64), e = new Uint8Array(48), sOut = new Uint8Array(32);

function desBlock(block: Uint8Array, off: number, out: Uint8Array) {
  for (let i = 0; i < 64; i++) tmp[i] = (block[off + (i >> 3)]! >> (7 - (i & 7))) & 1;
  for (let i = 0; i < 64; i++) bits[i] = tmp[IP[i]! - 1]!;
  // one Feistel round with zero subkey
  for (let i = 0; i < 48; i++) e[i] = bits[32 + E[i]! - 1]!;
  for (let i = 0; i < 8; i++) {
    const b = i * 6;
    const row = (e[b]! << 1) | e[b + 5]!;
    const col = (e[b + 1]! << 3) | (e[b + 2]! << 2) | (e[b + 3]! << 1) | e[b + 4]!;
    const v = S[i]![row * 16 + col]!;
    sOut[i * 4] = (v >> 3) & 1; sOut[i * 4 + 1] = (v >> 2) & 1; sOut[i * 4 + 2] = (v >> 1) & 1; sOut[i * 4 + 3] = v & 1;
  }
  for (let i = 0; i < 32; i++) tmp[i] = bits[i]! ^ sOut[P[i]! - 1]!;
  for (let i = 32; i < 64; i++) tmp[i] = bits[i]!;
  for (let i = 0; i < 64; i++) bits[i] = tmp[FP[i]! - 1]!;
  for (let i = 0; i < 8; i++) {
    let v = 0;
    for (let j = 0; j < 8; j++) v = (v << 1) | bits[i * 8 + j]!;
    out[off + i] = v;
  }
}

const SHUFFLE: Record<number, number> = { 0x00: 0x2b, 0x2b: 0x00, 0x6c: 0x80, 0x80: 0x6c, 0x01: 0x68, 0x68: 0x01, 0x48: 0x77, 0x77: 0x48, 0x60: 0xff, 0xff: 0x60, 0xb9: 0xc0, 0xc0: 0xb9, 0xfe: 0xeb, 0xeb: 0xfe };

function desDecryptFirstBlocks(data: Uint8Array) {
  const out = Uint8Array.from(data);
  const n = Math.min(data.length >> 3, 20);
  for (let i = 0; i < n; i++) desBlock(data, i * 8, out);
  return out;
}

function desDecryptMixed(data: Uint8Array, compSize: number) {
  let cycle = String(compSize).length;
  if (cycle < 3) cycle = 3; else if (cycle < 5) cycle += 1; else if (cycle < 7) cycle += 9; else cycle += 15;
  const out = Uint8Array.from(data);
  const nblocks = data.length >> 3;
  let j = 0;
  for (let i = 0; i < nblocks; i++) {
    const o = i * 8;
    if (i < 20 || i % cycle === 0) desBlock(data, o, out);
    else {
      if (j === 7) {
        j = 0;
        const b = data.subarray(o, o + 8);
        out[o] = b[3]!; out[o + 1] = b[4]!; out[o + 2] = b[6]!; out[o + 3] = b[0]!;
        out[o + 4] = b[1]!; out[o + 5] = b[2]!; out[o + 6] = b[5]!; out[o + 7] = SHUFFLE[b[7]!] ?? b[7]!;
      }
      j++;
    }
  }
  return out;
}
