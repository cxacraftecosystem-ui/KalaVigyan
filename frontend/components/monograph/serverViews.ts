import { PicturePlateView } from "@/components/monograph/kinds/plates/PicturePlateView";
import { Diagram } from "@/components/monograph/kinds/science/Diagram";
import { DipPlayer } from "@/components/monograph/kinds/science/DipPlayer";
import { EquationCard } from "@/components/monograph/kinds/science/EquationCard";
import { ModelExplainer } from "@/components/monograph/kinds/science/ModelExplainer";
import { Molecule3d } from "@/components/monograph/kinds/science/Molecule3d";
import { ProcessReplay } from "@/components/monograph/kinds/science/ProcessReplay";
import { ReactionPlayer } from "@/components/monograph/kinds/science/ReactionPlayer";
import { StagePlayer } from "@/components/monograph/kinds/science/StagePlayer";
import { StructureDiagram } from "@/components/monograph/kinds/science/StructureDiagram";
import type { ComponentViews } from "@/lib/componentViewContract";

export const SERVER_VIEWS: ComponentViews = {
  picture_plate: PicturePlateView,
  diagram: Diagram,
  dip_player: DipPlayer,
  equation_card: EquationCard,
  model_explainer: ModelExplainer,
  molecule_3d: Molecule3d,
  process_replay: ProcessReplay,
  reaction_player: ReactionPlayer,
  stage_player: StagePlayer,
  structure_diagram: StructureDiagram
};
