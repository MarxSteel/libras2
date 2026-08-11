// lib/gestures.js
// Biblioteca de gestos de Libras (POC) — keyframes em bones Mixamo.
//
// Cada gesto:
//   - duration: segundos
//   - bones: { boneName: [{ t: 0..1, euler: [X,Y,Z] }, ...] }
//
// Convenções Mixamo (T-pose, +X direita, +Y cima, +Z frente):
//   mixamorigRightArm:     rotaciona a partir do ombro
//     X < 0: levanta o braço pra FRENTE
//     X > 0: levanta o braço pra TRÁS
//     Y: gira cotovelo (yaw)
//     Z: gira o braço sobre o próprio eixo (roll)
//   mixamorigRightForeArm: rotaciona a partir do cotovelo
//     X < 0: dobra cotovelo pra FRENTE (flexão)
//   mixamorigRightHand:    rotaciona o punho
//   mixamorigHead:         X < 0: acena "sim"
//
// OBS: Soldier.glb tem mãos genéricas, sem dedos articulados. Sinais que
// dependem de configuração de dedos (letras A-Z, "EU TE AMO") ficam
// aproximados. Pra produção: trocar por modelo Mixamo com rig de dedos.

// ============================================================================
// GESTOS
// ============================================================================

/** OLA — palma aberta vai de um lado pro outro, altura do ombro */
const OLA = {
  duration: 1.6,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0,  0.0,  0.0] },
      { t: 0.20, euler: [-1.4,  0.0, -0.1] },  // braço pra frente
      { t: 0.45, euler: [-1.4,  0.5, -0.1] },  // cotovelo p/ direita
      { t: 0.65, euler: [-1.4, -0.5, -0.1] },  // cotovelo p/ esquerda
      { t: 0.85, euler: [-1.4,  0.5, -0.1] },
      { t: 1.00, euler: [-1.4, -0.5, -0.1] },
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.20, euler: [-0.6, 0.0, 0.0] },     // cotovelo flexionado
      { t: 1.00, euler: [-0.6, 0.0, 0.0] },
    ],
    'mixamorigRightHand':    [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.20, euler: [0.0, 0.0, -1.4] },     // palma pra frente
      { t: 1.00, euler: [0.0, 0.0, -1.4] },
    ],
  },
};

/** OBRIGADO — mão plana no queixo, vai pra frente em arco */
const OBRIGADO = {
  duration: 1.8,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.25, euler: [-1.2, 0.3, 0.0] },     // mão vai pro queixo
      { t: 0.45, euler: [-1.2, 0.3, 0.0] },     // toca queixo
      { t: 0.75, euler: [-0.8, 0.1, 0.0] },     // sai pra frente
      { t: 1.00, euler: [0.0, 0.0, 0.0] },      // volta pro corpo
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.25, euler: [-1.8, 0.0, 0.0] },     // cotovelo bem dobrado
      { t: 0.45, euler: [-1.8, 0.0, 0.0] },
      { t: 0.75, euler: [-1.0, 0.0, 0.0] },
      { t: 1.00, euler: [0.0, 0.0, 0.0] },
    ],
    'mixamorigRightHand':    [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.25, euler: [0.0, 0.0, -1.5] },     // palma pra cima
      { t: 0.75, euler: [0.0, 0.0, -0.5] },
      { t: 1.00, euler: [0.0, 0.0, 0.0] },
    ],
  },
};

/** SIM — cabeça acenando (movimento vertical) */
const SIM = {
  duration: 1.4,
  bones: {
    'mixamorigNeck': [
      { t: 0.00, euler: [0.0,  0.0, 0.0] },
      { t: 0.20, euler: [0.35, 0.0, 0.0] },     // cabeça pra baixo
      { t: 0.40, euler: [-0.2, 0.0, 0.0] },     // cabeça pra cima
      { t: 0.60, euler: [0.35, 0.0, 0.0] },
      { t: 0.80, euler: [-0.2, 0.0, 0.0] },
      { t: 1.00, euler: [0.0,  0.0, 0.0] },
    ],
  },
};

/** NAO — mão fechada balança lateral na altura do peito */
const NAO = {
  duration: 1.4,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0,  0.0,  0.0] },
      { t: 0.25, euler: [-0.6,  0.4,  0.0] },   // braço na frente do peito
      { t: 0.50, euler: [-0.6, -0.4,  0.0] },   // balança esquerda
      { t: 0.75, euler: [-0.6,  0.4,  0.0] },   // balança direita
      { t: 1.00, euler: [0.0,  0.0,  0.0] },
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.25, euler: [-1.6, 0.0, 0.0] },     // cotovelo dobrado
      { t: 1.00, euler: [-1.6, 0.0, 0.0] },
    ],
    'mixamorigRightHand':    [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.25, euler: [0.0, 0.0, 0.0] },      // mão fechada (aponta pra frente)
      { t: 1.00, euler: [0.0, 0.0, 0.0] },
    ],
  },
};

/** BOM DIA — mão aberta na testa, vai pra frente */
const BOM_DIA = {
  duration: 1.6,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0,  0.0,  0.0] },
      { t: 0.25, euler: [-2.4,  0.0,  0.0] },   // braço sobe pra testa
      { t: 0.50, euler: [-2.4,  0.0,  0.0] },   // toca testa
      { t: 0.80, euler: [-1.2,  0.0,  0.0] },   // estende pra frente
      { t: 1.00, euler: [0.0,  0.0,  0.0] },
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.25, euler: [-0.5, 0.0, 0.0] },     // cotovelo levemente dobrado
      { t: 0.80, euler: [-0.2, 0.0, 0.0] },
      { t: 1.00, euler: [0.0, 0.0, 0.0] },
    ],
    'mixamorigRightHand':    [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.25, euler: [0.0, 0.0, -1.4] },     // palma pra frente
      { t: 1.00, euler: [0.0, 0.0, -1.4] },
    ],
  },
};

/** TCHAU — mão aberta acena, palma pra frente */
const TCHAU = {
  duration: 1.4,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0,  0.0,  0.0] },
      { t: 0.20, euler: [-1.6,  0.0,  0.0] },   // braço levantado
      { t: 0.40, euler: [-1.6,  0.3,  0.0] },   // acena esquerda
      { t: 0.60, euler: [-1.6, -0.3,  0.0] },   // acena direita
      { t: 0.80, euler: [-1.6,  0.3,  0.0] },
      { t: 1.00, euler: [0.0,  0.0,  0.0] },
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.20, euler: [-0.4, 0.0, 0.0] },     // cotovelo levemente dobrado
      { t: 1.00, euler: [-0.4, 0.0, 0.0] },
    ],
    'mixamorigRightHand':    [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.20, euler: [0.0, 0.0, -1.4] },     // palma pra frente
      { t: 1.00, euler: [0.0, 0.0, -1.4] },
    ],
  },
};

/** EU — indicador aponta pro próprio peito */
const EU = {
  duration: 1.2,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0,  0.0, 0.0] },
      { t: 0.30, euler: [-0.3, 0.5, 0.0] },     // vai pro peito
      { t: 0.60, euler: [-0.3, 0.5, 0.0] },     // toca peito
      { t: 1.00, euler: [0.0,  0.0, 0.0] },
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.30, euler: [-1.8, 0.0, 0.0] },     // cotovelo bem dobrado
      { t: 1.00, euler: [-1.8, 0.0, 0.0] },
    ],
    'mixamorigRightHand':    [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.30, euler: [0.0, 0.0, 0.0] },      // aponta pra dentro
      { t: 1.00, euler: [0.0, 0.0, 0.0] },
    ],
  },
};

/** VOCE — indicador aponta pra frente */
const VOCE = {
  duration: 1.2,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0,  0.0,  0.0] },
      { t: 0.30, euler: [-1.4, -0.2, 0.0] },    // braço estende pra frente
      { t: 0.60, euler: [-1.4, -0.2, 0.0] },    // aponta
      { t: 1.00, euler: [0.0,  0.0,  0.0] },
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.30, euler: [-0.2, 0.0, 0.0] },      // cotovelo levemente dobrado
      { t: 1.00, euler: [-0.2, 0.0, 0.0] },
    ],
    'mixamorigRightHand':    [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.30, euler: [0.0, 0.0, 0.0] },       // aponta pra frente
      { t: 1.00, euler: [0.0, 0.0, 0.0] },
    ],
  },
};

/** AMIGO — braços se cruzam na frente (interpretação simplificada) */
const AMIGO = {
  duration: 1.6,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0,  0.0,  0.0] },
      { t: 0.30, euler: [-0.8,  0.6,  0.0] },   // cruza pro lado esquerdo
      { t: 0.70, euler: [-0.8,  0.6,  0.0] },
      { t: 1.00, euler: [0.0,  0.0,  0.0] },
    ],
    'mixamorigLeftArm':      [
      { t: 0.00, euler: [0.0,  0.0,  0.0] },
      { t: 0.30, euler: [-0.8, -0.6,  0.0] },   // cruza pro lado direito
      { t: 0.70, euler: [-0.8, -0.6,  0.0] },
      { t: 1.00, euler: [0.0,  0.0,  0.0] },
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.30, euler: [-1.4, 0.0, 0.0] },
      { t: 1.00, euler: [-1.4, 0.0, 0.0] },
    ],
    'mixamorigLeftForeArm':  [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.30, euler: [-1.4, 0.0, 0.0] },
      { t: 1.00, euler: [-1.4, 0.0, 0.0] },
    ],
  },
};

/** POR_FAVOR — mão no peito, movimento circular (aproximação) */
const POR_FAVOR = {
  duration: 1.8,
  bones: {
    'mixamorigRightArm':     [
      { t: 0.00, euler: [0.0,  0.0, 0.0] },
      { t: 0.30, euler: [-0.4, 0.5, 0.0] },     // vai pro peito
      { t: 0.50, euler: [-0.4, 0.5, 0.0] },
      { t: 0.70, euler: [-0.2, 0.6, 0.0] },     // gira um pouco
      { t: 0.85, euler: [-0.4, 0.4, 0.0] },
      { t: 1.00, euler: [0.0,  0.0, 0.0] },
    ],
    'mixamorigRightForeArm': [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.30, euler: [-1.7, 0.0, 0.0] },
      { t: 1.00, euler: [-1.7, 0.0, 0.0] },
    ],
    'mixamorigRightHand':    [
      { t: 0.00, euler: [0.0, 0.0, 0.0] },
      { t: 0.30, euler: [0.0, 0.0, -1.3] },
      { t: 1.00, euler: [0.0, 0.0, -1.3] },
    ],
  },
};

// ============================================================================
// REGISTRO
// ============================================================================

export const GESTURES = {
  'OLA': OLA,
  'OLÁ': OLA,
  'OBRIGADO': OBRIGADO,
  'OBRIGADA': OBRIGADO,
  'SIM': SIM,
  'NAO': NAO,
  'NÃO': NAO,
  'BOM': BOM_DIA,
  'DIA': BOM_DIA,
  'BOM_DIA': BOM_DIA,
  'BOMDIA': BOM_DIA,
  'TCHAU': TCHAU,
  'TCHAUZINHO': TCHAU,
  'EU': EU,
  'EU_MESMO': EU,
  'VOCE': VOCE,
  'VOCÊ': VOCE,
  'TU': VOCE,
  'AMIGO': AMIGO,
  'AMIGA': AMIGO,
  'AMIGOS': AMIGO,
  'POR_FAVOR': POR_FAVOR,
  'PORFAVOR': POR_FAVOR,
  'FAVOR': POR_FAVOR,
};

/**
 * Normaliza token pra lookup (lowercase, sem acento, _ no lugar de espaço).
 */
export function normalizeToken(tok) {
  return tok
    .toUpperCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')  // remove acentos
    .replace(/\s+/g, '_')
    .trim();
}

/**
 * Procura gesto por token. Suporta compostos (BOM DIA → BOM_DIA).
 *
 * @param {string} word - palavra/frase a procurar
 * @param {string[]} [nextWords] - próximas palavras (pra compostos)
 * @returns {{ gesture: Object, normalized: string, consumed: number } | null}
 */
export function lookupGesture(word, nextWords = []) {
  // tenta composto (word + next)
  for (let n = Math.min(2, nextWords.length); n >= 1; n--) {
    const compound = [word, ...nextWords.slice(0, n)]
      .map(normalizeToken)
      .join('_');
    if (GESTURES[compound]) {
      return { gesture: GESTURES[compound], normalized: compound, consumed: n + 1 };
    }
  }
  // tenta simples
  const norm = normalizeToken(word);
  if (GESTURES[norm]) {
    return { gesture: GESTURES[norm], normalized: norm, consumed: 1 };
  }
  return null;
}
