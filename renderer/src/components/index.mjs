import { AnimatedFlowDiagram } from "./AnimatedFlowDiagram.jsx";
import { BulletReveal } from "./BulletReveal.jsx";
import { Callout } from "./Callout.jsx";
import { ChapterTitle } from "./ChapterTitle.jsx";
import { CodeBlock } from "./CodeBlock.jsx";
import { Comparison } from "./Comparison.jsx";
import { DefinitionCard } from "./DefinitionCard.jsx";
import { IconGrid } from "./IconGrid.jsx";
import { ImagePan, SeriesAsset } from "./ImagePan.jsx";
import { Outro } from "./Outro.jsx";
import { StatCounter } from "./StatCounter.jsx";
import { Terminal } from "./Terminal.jsx";
import { Timeline } from "./Timeline.jsx";

// The closed component enum. A manifest naming anything else fails the render.
export const COMPONENTS = {
  DefinitionCard,
  AnimatedFlowDiagram,
  BulletReveal,
  ImagePan,
  SeriesAsset,
  ChapterTitle,
  Outro,
  CodeBlock,
  Terminal,
  Comparison,
  StatCounter,
  Timeline,
  Callout,
  IconGrid,
};
// Components that own the whole frame and skip the shared header/title.
export const FULL_FRAME = new Set(["ChapterTitle"]);
