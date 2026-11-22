import type * as ThreeDmolModule from "3dmol";

type ThreeDmol = typeof ThreeDmolModule;
type GLViewer = ThreeDmolModule.GLViewer;

export type MoleculeScene = {
  turn: (degrees: number, milliseconds: number) => void;
  tilt: (degrees: number, milliseconds: number) => void;
  zoom: (factor: number, milliseconds: number) => void;
  dispose: () => void;
};
export type MoleculeViewer = { show: (element: HTMLElement, sdf: string) => MoleculeScene | null };
export type SceneViewer = Pick<GLViewer, "rotate" | "zoom" | "getCanvas" | "clear">;

export const MOLECULE_STYLE = { stick: { radius: 0.14 }, sphere: { scale: 0.24 } } as const;
export const VIEWER_SPEC = { backgroundAlpha: 0, antialias: true } as const;
export const TURN_AXIS = "y";
export const TILT_AXIS = "x";

let loading: Promise<MoleculeViewer> | null = null;

function contextOf(canvas: HTMLCanvasElement): WebGLRenderingContext | WebGL2RenderingContext | null {
  return canvas.getContext("webgl2") ?? canvas.getContext("webgl");
}

function release(canvas: HTMLCanvasElement): void {
  contextOf(canvas)?.getExtension("WEBGL_lose_context")?.loseContext();
}

export function webglAvailable(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    if (!contextOf(canvas)) return false;
    release(canvas);
    return true;
  } catch (cause) {
    console.warn(cause);
    return false;
  }
}

export function moleculeScene(viewer: SceneViewer, element: HTMLElement): MoleculeScene {
  return {
    turn(degrees, milliseconds) {
      viewer.rotate(degrees, TURN_AXIS, milliseconds);
    },
    tilt(degrees, milliseconds) {
      viewer.rotate(degrees, TILT_AXIS, milliseconds);
    },
    zoom(factor, milliseconds) {
      viewer.zoom(factor, milliseconds);
    },
    dispose() {
      const canvas = viewer.getCanvas();
      viewer.clear();
      release(canvas);
      element.replaceChildren();
    }
  };
}

function created(api: ThreeDmol, element: HTMLElement): GLViewer | null {
  try {
    return api.createViewer(element, { ...VIEWER_SPEC }) ?? null;
  } catch (cause) {
    console.warn(cause);
    return null;
  }
}

function viewerOf(module: ThreeDmol & { default?: ThreeDmol }): MoleculeViewer {
  const api = typeof module.createViewer === "function" ? module : module.default;
  if (!api || typeof api.createViewer !== "function") throw new Error("3Dmol.js loaded without createViewer");
  return {
    show(element, sdf) {
      const viewer = created(api, element);
      if (!viewer) return null;
      viewer.addModel(sdf, "sdf");
      viewer.setStyle({}, { stick: { ...MOLECULE_STYLE.stick }, sphere: { ...MOLECULE_STYLE.sphere } });
      viewer.zoomTo();
      viewer.render();
      return moleculeScene(viewer, element);
    }
  };
}

export function loadMoleculeViewer(): Promise<MoleculeViewer> {
  loading ??= import("3dmol").then(viewerOf).catch((cause: unknown) => {
    loading = null;
    throw cause;
  });
  return loading;
}
