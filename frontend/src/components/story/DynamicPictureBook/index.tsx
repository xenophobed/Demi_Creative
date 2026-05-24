import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import type { StoryContent } from "@/types/api";
import { useStreamVisualizationContext } from "@/providers/StreamVisualizationProvider";

export interface PictureBookPage {
  id: string;
  text: string;
}

export function splitStoryIntoPictureBookPages(
  text: string,
  maxChars = 280,
): PictureBookPage[] {
  const normalized = text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n\n");

  if (!normalized) return [];

  const paragraphs = normalized.split(/\n\n+/);
  const pages: string[] = [];
  let current = "";

  paragraphs.forEach((paragraph) => {
    if (!current) {
      current = paragraph;
      return;
    }

    if (`${current}\n\n${paragraph}`.length <= maxChars) {
      current = `${current}\n\n${paragraph}`;
      return;
    }

    pages.push(current);
    current = paragraph;
  });

  if (current) pages.push(current);

  return pages.flatMap((page, pageIndex) => {
    if (page.length <= maxChars * 1.35) {
      return [{ id: `page-${pageIndex}`, text: page }];
    }

    const sentences = page.match(/[^。！？.!?]+[。！？.!?]?/g) ?? [page];
    const splitPages: PictureBookPage[] = [];
    let chunk = "";

    sentences.forEach((sentence) => {
      const next = `${chunk}${sentence}`.trim();
      if (chunk && next.length > maxChars) {
        splitPages.push({
          id: `page-${pageIndex}-${splitPages.length}`,
          text: chunk.trim(),
        });
        chunk = sentence.trim();
      } else {
        chunk = next;
      }
    });

    if (chunk) {
      splitPages.push({
        id: `page-${pageIndex}-${splitPages.length}`,
        text: chunk.trim(),
      });
    }

    return splitPages;
  });
}

export function isPictureBookAutoplayAllowed(
  prefersReducedMotion: boolean,
  pageCount: number,
): boolean {
  return !prefersReducedMotion && pageCount > 1;
}

interface DynamicPictureBookProps {
  story: StoryContent;
  title: string;
  imageUrl?: string | null;
}

function DynamicPictureBook({ story, title, imageUrl }: DynamicPictureBookProps) {
  const { prefersReducedMotion } = useStreamVisualizationContext();
  const [pageIndex, setPageIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const pages = useMemo(
    () => splitStoryIntoPictureBookPages(story.text),
    [story.text],
  );
  const page = pages[pageIndex];
  const canGoBack = pageIndex > 0;
  const canGoForward = pageIndex < pages.length - 1;

  useEffect(() => {
    if (
      !isPlaying ||
      !isPictureBookAutoplayAllowed(prefersReducedMotion, pages.length)
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      setPageIndex((current) => {
        if (current >= pages.length - 1) {
          setIsPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 4200);

    return () => window.clearInterval(timer);
  }, [isPlaying, pages.length, prefersReducedMotion]);

  const goBack = () => setPageIndex((current) => Math.max(current - 1, 0));
  const goForward = () =>
    setPageIndex((current) => Math.min(current + 1, pages.length - 1));

  if (!page) return null;

  return (
    <section
      className="dynamic-picture-book"
      aria-label="Dynamic picture book fallback"
    >
      <div className="picture-book-stage">
        {imageUrl && (
          <motion.img
            src={imageUrl}
            alt=""
            className="picture-book-art"
            animate={
              prefersReducedMotion
                ? undefined
                : { scale: isPlaying ? [1, 1.035, 1] : 1 }
            }
            transition={{ duration: 4, repeat: isPlaying ? Infinity : 0 }}
          />
        )}

        <div className="picture-book-page">
          <p className="picture-book-kicker">Picture-book mode</p>
          <h2>{title}</h2>
          <AnimatePresence mode="wait">
            <motion.div
              key={page.id}
              initial={prefersReducedMotion ? false : { opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={prefersReducedMotion ? undefined : { opacity: 0, x: -24 }}
              transition={{ duration: 0.28 }}
              className="picture-book-text"
            >
              {page.text.split("\n\n").map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <div className="picture-book-controls">
        <button
          type="button"
          onClick={goBack}
          disabled={!canGoBack}
          aria-label="Previous picture-book page"
          title="Previous"
        >
          <ChevronLeft size={20} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => setIsPlaying((current) => !current)}
          disabled={
            !isPictureBookAutoplayAllowed(prefersReducedMotion, pages.length)
          }
          aria-label={
            isPlaying
              ? "Pause picture-book playback"
              : "Play picture-book playback"
          }
          title={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? (
            <Pause size={20} aria-hidden="true" />
          ) : (
            <Play size={20} aria-hidden="true" />
          )}
        </button>
        <button
          type="button"
          onClick={goForward}
          disabled={!canGoForward}
          aria-label="Next picture-book page"
          title="Next"
        >
          <ChevronRight size={20} aria-hidden="true" />
        </button>
        <span>
          {pageIndex + 1}/{pages.length}
        </span>
      </div>
    </section>
  );
}

export default DynamicPictureBook;
