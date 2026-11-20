"use client";

import { useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

import { motionAllowedNow } from "@/components/motion/useMotionAllowed";
import { IconButton } from "@/components/ui/IconButton";
import { chapterFromQuery, currentChapter, type Chapter } from "@/lib/chapters";
import { railArrowShown, railEnds, railMask, railStep, railTarget, type RailArrow, type RailEnds } from "@/lib/monographRail";

const NO_ALIASES: Readonly<Record<string, string>> = {};

export const CHAPTER_RAIL_ARROWS: Readonly<Record<RailArrow, { label: string; path: string; sign: 1 | -1 }>> = {
  back: { label: "Show earlier chapters", path: "M10 3 L5 8 L10 13", sign: -1 },
  on: { label: "Show later chapters", path: "M6 3 L11 8 L6 13", sign: 1 }
};

type RailState = RailEnds & { rtl: boolean };

function railLine(): number {
  const rail = document.querySelector<HTMLElement>("[data-chapter-rail]");
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  return (rail?.offsetHeight ?? 0) + rem;
}

function useChapterInView(chapters: readonly Chapter[]): string | null {
  const [current, setCurrent] = useState<string | null>(chapters[0]?.id ?? null);
  useEffect(() => {
    let frame = 0;
    const measure = () => {
      frame = 0;
      const tops = chapters.flatMap((chapter) => {
        const node = document.getElementById(chapter.id);
        return node ? [{ id: chapter.id, top: node.getBoundingClientRect().top }] : [];
      });
      setCurrent(currentChapter(tops, railLine()));
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, [chapters]);
  return current;
}

function keepFocus(list: HTMLOListElement, ends: RailEnds): void {
  const focused = document.activeElement;
  if (!(focused instanceof HTMLElement) || focused.parentElement !== list.parentElement) return;
  const arrow = focused.dataset.go;
  if ((arrow !== "back" && arrow !== "on") || railArrowShown(ends, arrow)) return;
  const other: RailArrow = arrow === "back" ? "on" : "back";
  const next = railArrowShown(ends, other) ? list.parentElement?.querySelector<HTMLElement>(`[data-go="${other}"]`) : (list.querySelector<HTMLElement>('a[aria-current="location"]') ?? list.querySelector<HTMLElement>("a"));
  next?.focus();
}

function useRailState(list: RefObject<HTMLOListElement | null>): RailState | null {
  const [state, setState] = useState<RailState | null>(null);
  useEffect(() => {
    const node = list.current;
    if (!node) return;
    let frame = 0;
    const measure = () => {
      frame = 0;
      const ends = railEnds(node.scrollLeft, node.scrollWidth, node.clientWidth);
      keepFocus(node, ends);
      setState({ ...ends, rtl: getComputedStyle(node).direction === "rtl" });
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    node.addEventListener("scroll", schedule, { passive: true });
    const sizes = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
    [node, ...node.children].forEach((child) => sizes?.observe(child));
    return () => {
      if (frame) cancelAnimationFrame(frame);
      node.removeEventListener("scroll", schedule);
      sizes?.disconnect();
    };
  }, [list]);
  return state;
}

function useCurrentShown(list: RefObject<HTMLOListElement | null>, current: string | null): void {
  useEffect(() => {
    const node = list.current;
    const link = node?.querySelector<HTMLElement>('a[aria-current="location"]');
    if (!node || !link || node.scrollWidth <= node.clientWidth + 1) return;
    const left = railTarget(node.getBoundingClientRect(), link.getBoundingClientRect(), node.scrollLeft);
    if (left !== null) node.scrollTo({ left, behavior: motionAllowedNow() ? "smooth" : "auto" });
  }, [list, current]);
}

function maskStyle(state: RailState | null): CSSProperties | undefined {
  if (!state) return undefined;
  const mask = railMask(state, state.rtl);
  return { maskImage: mask, WebkitMaskImage: mask };
}

function ArrowGlyph({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden className="rtl:-scale-x-100">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type ArrowProps = { arrow: RailArrow; state: RailState; list: RefObject<HTMLOListElement | null> };

function RailArrowButton({ arrow, state, list }: ArrowProps) {
  const shown = railArrowShown(state, arrow);
  const { label, path, sign } = CHAPTER_RAIL_ARROWS[arrow];
  const press = () => {
    const node = list.current;
    if (!node) return;
    node.scrollBy({ left: sign * (state.rtl ? -1 : 1) * railStep(node.clientWidth), behavior: motionAllowedNow() ? "smooth" : "auto" });
  };
  return <IconButton label={label} icon={<ArrowGlyph path={path} />} onClick={press} hidden={!shown} data-go={arrow} className="shrink-0 self-center text-indigo hover:text-indigo-hover" />;
}

export function ChapterRail({ chapters, label = "Chapters", aliases = NO_ALIASES }: { chapters: readonly Chapter[]; label?: string; aliases?: Readonly<Record<string, string>> }) {
  const current = useChapterInView(chapters);
  const list = useRef<HTMLOListElement>(null);
  const state = useRailState(list);
  useCurrentShown(list, current);

  useEffect(() => {
    if (window.location.hash) return;
    const target = chapterFromQuery(window.location.search, aliases, chapters);
    if (target) document.getElementById(target)?.scrollIntoView({ behavior: motionAllowedNow() ? "smooth" : "auto", block: "start" });
  }, [aliases, chapters]);

  return (
    <nav aria-label={label} className="kv-chapters" data-chapter-rail="" data-testid="chapter-rail">
      <div className="flex items-stretch">
        {state?.over ? <RailArrowButton arrow="back" state={state} list={list} /> : null}
        <ol ref={list} className="min-w-0 flex-1" style={maskStyle(state)}>
          {chapters.map((chapter, index) => (
            <li key={chapter.id}>
              <a href={`#${chapter.id}`} aria-current={chapter.id === current ? "location" : undefined}>
                <b>{index + 1}</b>
                {chapter.label}
              </a>
            </li>
          ))}
        </ol>
        {state?.over ? <RailArrowButton arrow="on" state={state} list={list} /> : null}
      </div>
    </nav>
  );
}
