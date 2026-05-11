/**
 * PrepPipe WebGAL 自定义 Pixi perform（骨架实现）
 *
 * TODO(WebGAL): 当前 `codegen_webgal` 对特效 IR 一律报错，导出不会自动复制本文件；待后端恢复后再启用 `export_webgal` 的 `_copy_preppipe_runtime`。
 *
 * - 目标态：`export_webgal` 将本文件复制到输出工程的 `game/prepipe/prepipePerform.ts`。
 * - 官方 WebGAL 不会自动加载此路径；请把本文件合并进 WebGAL 源码
 *   `Core/gameScripts/pixiPerformScripts/prepipePerform.ts`，并在 `index.ts` 中 `import './prepipePerform'`，
 *   再执行 `yarn run build`。
 *
 * 以下为类型占位；真实构建请使用 WebGAL 源码中的 registerPerform、PIXI、WebGAL 类型定义。
 */
// import * as PIXI from 'pixi.js';
// import { registerPerform } from '../pixiPerformManager';

declare const WebGAL: {
  game: {
    userData: Record<string, string>;
  };
};

function readNum(key: string, def: number): number {
  const v = WebGAL.game.userData[key];
  if (v === undefined || v === '') return def;
  const n = Number(v);
  return Number.isFinite(n) ? n : def;
}

function readStr(key: string, def: string): string {
  const v = WebGAL.game.userData[key];
  return v === undefined || v === '' ? def : String(v);
}

/*
registerPerform('prepipeWeather', {
  fg: () => {
    const kind = readStr('prepipe_weather_kind', 'snow').toLowerCase();
    const intensity = readNum('prepipe_weather_intensity', 40);
    void intensity;
    void kind;
    // TODO: 使用 PIXI 粒子系统实现 snow/rain，读取 vx/vy、fade 参数
  },
});

registerPerform('prepipeCharTrembleLoop', {
  fg: () => {
    void readStr('prepipe_tremble_target', '');
    void readNum('prepipe_tremble_amp', 4);
    void readNum('prepipe_tremble_period', 0.1);
    // TODO: 按 target 在立绘容器上挂接往复位移，直至 pixiInit 或显式停止
  },
});

registerPerform('prepipeCharTrembleStop', {
  fg: () => {
    void readStr('prepipe_tremble_target', '');
    // TODO: 移除该 target 上由 prepipeCharTrembleLoop 挂接的位移（无操作则安全返回）
  },
});

registerPerform('prepipeFlash', {
  fg: () => {
    void readStr('prepipe_flash_color', '#ffffff');
    void readNum('prepipe_flash_fi', 0.1);
    void readNum('prepipe_flash_hold', 0.2);
    void readNum('prepipe_flash_fo', 0.1);
    // TODO: 全屏色块 alpha 动画，与 Ren'Py preppipe_flash_screen 时长一致
  },
});
*/

export {};
