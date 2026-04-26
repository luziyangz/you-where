const VERSION = 4;
const SIZE = VERSION * 4 + 17;
const DATA_CODEWORDS = 80;
const EC_CODEWORDS = 20;

const encodeUtf8 = (text) => {
  const bytes = [];
  for (let i = 0; i < text.length; i += 1) {
    let code = text.charCodeAt(i);
    if (code >= 0xD800 && code <= 0xDBFF && i + 1 < text.length) {
      const next = text.charCodeAt(i + 1);
      if (next >= 0xDC00 && next <= 0xDFFF) {
        code = 0x10000 + ((code - 0xD800) << 10) + (next - 0xDC00);
        i += 1;
      }
    }

    if (code < 0x80) {
      bytes.push(code);
    } else if (code < 0x800) {
      bytes.push(0xC0 | (code >> 6), 0x80 | (code & 0x3F));
    } else if (code < 0x10000) {
      bytes.push(0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F));
    } else {
      bytes.push(
        0xF0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3F),
        0x80 | ((code >> 6) & 0x3F),
        0x80 | (code & 0x3F)
      );
    }
  }
  return bytes;
};

const appendBits = (bits, value, length) => {
  for (let i = length - 1; i >= 0; i -= 1) {
    bits.push(((value >>> i) & 1) === 1);
  }
};

const toDataCodewords = (text) => {
  const bytes = encodeUtf8(text);
  if (bytes.length > 78) {
    throw new Error('QR payload is too long');
  }

  const bits = [];
  appendBits(bits, 0x4, 4); // byte mode
  appendBits(bits, bytes.length, 8);
  bytes.forEach((byte) => appendBits(bits, byte, 8));

  const capacityBits = DATA_CODEWORDS * 8;
  const terminator = Math.min(4, capacityBits - bits.length);
  appendBits(bits, 0, terminator);
  while (bits.length % 8 !== 0) {
    bits.push(false);
  }

  const data = [];
  for (let i = 0; i < bits.length; i += 8) {
    let value = 0;
    for (let j = 0; j < 8; j += 1) {
      value = (value << 1) | (bits[i + j] ? 1 : 0);
    }
    data.push(value);
  }

  for (let pad = 0; data.length < DATA_CODEWORDS; pad += 1) {
    data.push(pad % 2 === 0 ? 0xEC : 0x11);
  }
  return data;
};

const buildGfTables = () => {
  const exp = new Array(512).fill(0);
  const log = new Array(256).fill(0);
  let value = 1;
  for (let i = 0; i < 255; i += 1) {
    exp[i] = value;
    log[value] = i;
    value <<= 1;
    if (value & 0x100) {
      value ^= 0x11D;
    }
  }
  for (let i = 255; i < 512; i += 1) {
    exp[i] = exp[i - 255];
  }
  return { exp, log };
};

const GF = buildGfTables();

const gfMultiply = (x, y) => {
  if (x === 0 || y === 0) {
    return 0;
  }
  return GF.exp[GF.log[x] + GF.log[y]];
};

const reedSolomonDivisor = (degree) => {
  const result = new Array(degree).fill(0);
  result[degree - 1] = 1;
  let root = 1;
  for (let i = 0; i < degree; i += 1) {
    for (let j = 0; j < degree; j += 1) {
      result[j] = gfMultiply(result[j], root);
      if (j + 1 < degree) {
        result[j] ^= result[j + 1];
      }
    }
    root = gfMultiply(root, 0x02);
  }
  return result;
};

const reedSolomonRemainder = (data, divisor) => {
  const result = new Array(divisor.length).fill(0);
  data.forEach((byte) => {
    const factor = byte ^ result.shift();
    result.push(0);
    divisor.forEach((coef, index) => {
      result[index] ^= gfMultiply(coef, factor);
    });
  });
  return result;
};

const buildCodewords = (text) => {
  const data = toDataCodewords(text);
  const ec = reedSolomonRemainder(data, reedSolomonDivisor(EC_CODEWORDS));
  return data.concat(ec);
};

const blankMatrix = () => ({
  modules: Array.from({ length: SIZE }, () => new Array(SIZE).fill(false)),
  reserved: Array.from({ length: SIZE }, () => new Array(SIZE).fill(false))
});

const setModule = (state, x, y, dark, reserve = true) => {
  if (x < 0 || y < 0 || x >= SIZE || y >= SIZE) {
    return;
  }
  state.modules[y][x] = !!dark;
  if (reserve) {
    state.reserved[y][x] = true;
  }
};

const drawFinder = (state, x, y) => {
  for (let yy = -1; yy <= 7; yy += 1) {
    for (let xx = -1; xx <= 7; xx += 1) {
      setModule(state, x + xx, y + yy, false, true);
    }
  }
  for (let yy = 0; yy < 7; yy += 1) {
    for (let xx = 0; xx < 7; xx += 1) {
      const dark = xx === 0 || xx === 6 || yy === 0 || yy === 6 || (xx >= 2 && xx <= 4 && yy >= 2 && yy <= 4);
      setModule(state, x + xx, y + yy, dark, true);
    }
  }
};

const drawAlignment = (state, cx, cy) => {
  for (let y = -2; y <= 2; y += 1) {
    for (let x = -2; x <= 2; x += 1) {
      const dark = Math.max(Math.abs(x), Math.abs(y)) === 2 || (x === 0 && y === 0);
      setModule(state, cx + x, cy + y, dark, true);
    }
  }
};

const drawFunctionPatterns = (state) => {
  drawFinder(state, 0, 0);
  drawFinder(state, SIZE - 7, 0);
  drawFinder(state, 0, SIZE - 7);

  for (let i = 8; i < SIZE - 8; i += 1) {
    const dark = i % 2 === 0;
    setModule(state, i, 6, dark, true);
    setModule(state, 6, i, dark, true);
  }

  drawAlignment(state, 26, 26);
  setModule(state, 8, SIZE - 8, true, true);

  // Reserve format information areas. Actual bits are written after masking.
  for (let i = 0; i < 9; i += 1) {
    if (i !== 6) {
      setModule(state, 8, i, false, true);
      setModule(state, i, 8, false, true);
    }
  }
  for (let i = 0; i < 8; i += 1) {
    setModule(state, SIZE - 1 - i, 8, false, true);
    setModule(state, 8, SIZE - 1 - i, false, true);
  }
};

const codewordsToBits = (codewords) => {
  const bits = [];
  codewords.forEach((byte) => appendBits(bits, byte, 8));
  return bits;
};

const applyMask0 = (x, y) => (x + y) % 2 === 0;

const drawCodewords = (state, codewords) => {
  const bits = codewordsToBits(codewords);
  let bitIndex = 0;
  let upward = true;

  for (let right = SIZE - 1; right >= 1; right -= 2) {
    if (right === 6) {
      right -= 1;
    }

    for (let vert = 0; vert < SIZE; vert += 1) {
      const y = upward ? SIZE - 1 - vert : vert;
      for (let j = 0; j < 2; j += 1) {
        const x = right - j;
        if (state.reserved[y][x]) {
          continue;
        }
        const rawBit = bitIndex < bits.length ? bits[bitIndex] : false;
        bitIndex += 1;
        setModule(state, x, y, rawBit !== applyMask0(x, y), false);
      }
    }
    upward = !upward;
  }
};

const bchFormatBits = (data) => {
  let value = data << 10;
  const generator = 0x537;
  for (let i = 14; i >= 10; i -= 1) {
    if (((value >>> i) & 1) !== 0) {
      value ^= generator << (i - 10);
    }
  }
  return ((data << 10) | value) ^ 0x5412;
};

const getBit = (value, index) => ((value >>> index) & 1) !== 0;

const drawFormatBits = (state) => {
  const format = bchFormatBits(0x08); // error correction L + mask 0
  for (let i = 0; i <= 5; i += 1) {
    setModule(state, 8, i, getBit(format, i), true);
  }
  setModule(state, 8, 7, getBit(format, 6), true);
  setModule(state, 8, 8, getBit(format, 7), true);
  setModule(state, 7, 8, getBit(format, 8), true);
  for (let i = 9; i < 15; i += 1) {
    setModule(state, 14 - i, 8, getBit(format, i), true);
  }
  for (let i = 0; i < 8; i += 1) {
    setModule(state, SIZE - 1 - i, 8, getBit(format, i), true);
  }
  for (let i = 8; i < 15; i += 1) {
    setModule(state, 8, SIZE - 15 + i, getBit(format, i), true);
  }
  setModule(state, 8, SIZE - 8, true, true);
};

const createQrMatrix = (text) => {
  const state = blankMatrix();
  drawFunctionPatterns(state);
  drawCodewords(state, buildCodewords(text));
  drawFormatBits(state);
  return state.modules;
};

module.exports = {
  createQrMatrix
};
