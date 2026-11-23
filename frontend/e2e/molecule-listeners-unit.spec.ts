import { expect, test } from "@playwright/test";

import { heldListeners, moleculeScene, type SceneViewer } from "@/lib/moleculeViewer";

function counted(target: EventTarget, type: string, heard: string[], name: string): void {
  target.addEventListener(type, () => heard.push(name));
}

test("the listeners a viewer adds to the page while it is made are removed when its scene is disposed", () => {
  const body = new EventTarget();
  const page = new EventTarget();
  const heard: string[] = [];
  const { made, held } = heldListeners([body, page], () => {
    counted(body, "mouseup", heard, "mouseup");
    counted(body, "touchend", heard, "touchend");
    counted(page, "resize", heard, "resize");
    return "viewer";
  });
  expect(made).toBe("viewer");
  expect(held.map(({ type }) => type)).toEqual(["mouseup", "touchend", "resize"]);
  for (const type of ["mouseup", "touchend"]) body.dispatchEvent(new Event(type));
  page.dispatchEvent(new Event("resize"));
  expect(heard).toEqual(["mouseup", "touchend", "resize"]);

  const viewer = { rotate: () => undefined, zoom: () => undefined, getCanvas: () => ({ getContext: () => null }), clear: () => undefined } as unknown as SceneViewer;
  const element = { replaceChildren: () => undefined } as unknown as HTMLElement;
  moleculeScene(viewer, element, held).dispose();
  for (const type of ["mouseup", "touchend"]) body.dispatchEvent(new Event(type));
  page.dispatchEvent(new Event("resize"));
  expect(heard).toEqual(["mouseup", "touchend", "resize"]);
});

test("watching a viewer being made leaves the page's own listeners and addEventListener as they were", () => {
  const body = new EventTarget();
  const heard: string[] = [];
  counted(body, "mouseup", heard, "the page's own");
  heldListeners([body], () => counted(body, "mouseup", heard, "the viewer's"));
  expect(Object.prototype.hasOwnProperty.call(body, "addEventListener")).toBe(false);
  counted(body, "mouseup", heard, "added afterwards");
  body.dispatchEvent(new Event("mouseup"));
  expect(heard).toEqual(["the page's own", "the viewer's", "added afterwards"]);
});

test("a viewer that fails while it is made still gives addEventListener back", () => {
  const body = new EventTarget();
  expect(() =>
    heldListeners([body], () => {
      throw new Error("no WebGL");
    })
  ).toThrow("no WebGL");
  expect(Object.prototype.hasOwnProperty.call(body, "addEventListener")).toBe(false);
});
