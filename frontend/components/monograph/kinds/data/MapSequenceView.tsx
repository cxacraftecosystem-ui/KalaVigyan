import { Fragment } from "react";

import { HeldOrUnitText, HeldText } from "@/components/monograph/kinds/plates/HeldText";
import { heldComponent, type NestingViewProps } from "@/components/monograph/kinds/plates/nesting";
import { mapSequenceShape, type SequenceCard, type SequenceItem } from "@/lib/componentSpecsData";
import { parseShape } from "@/lib/shape";

import { FigureHeadView, labelledBy, TextLineView, TextLines } from "./DataParts";

function Card({ card, props }: { card: SequenceCard; props: NestingViewProps }) {
  const renderUnit = props.renderUnit;
  return (
    <li className="ws-card">
      {card.visual ? <div className="ws-vis">{heldComponent(props, card.visual)}</div> : null}
      <p className="when">{renderUnit(card.when)}</p>
      <h3>{renderUnit(card.title)}</h3>
      <TextLines lines={card.lines} renderUnit={renderUnit} />
      {card.differs ? (
        <details className="differs">
          <summary className="differ">
            <HeldText nodes={card.differs.summary} />
          </summary>
          <div className="differs-body">
            <HeldOrUnitText value={card.differs.body} renderUnit={renderUnit} />
          </div>
        </details>
      ) : null}
    </li>
  );
}

function Items({ items, props }: { items: SequenceItem[]; props: NestingViewProps }) {
  return (
    <>
      {items.map((item, index) =>
        item.card ? <Card key={item.card.title} card={item.card} props={props} /> : <Fragment key={item.component ?? index}>{heldComponent(props, item.component)}</Fragment>
      )}
    </>
  );
}

export function MapSequenceView(props: NestingViewProps) {
  const sequence = parseShape(mapSequenceShape, props.spec);
  const renderUnit = props.renderUnit;
  return (
    <figure className="fig ws-fig" aria-labelledby={labelledBy(sequence.head)}>
      <FigureHeadView head={sequence.head} renderUnit={renderUnit} />
      <ol className="ws">
        <Items items={sequence.first} props={props} />
      </ol>
      <TextLineView line={sequence.source} renderUnit={renderUnit} />
      {sequence.more.length ? (
        <ol className="ws ws-more">
          <Items items={sequence.more} props={props} />
        </ol>
      ) : null}
    </figure>
  );
}
