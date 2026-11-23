import { citationShape, craftLinkShape, type CraftLink } from "@/lib/answerShapes";
import { envelope, explainerSentenceShape, type BlockEnvelope, type ExplainerSentence } from "@/lib/explainerBlockBase";
import { districtShape, type DistrictRef } from "@/lib/explainerPlace";
import { datasetShape, type RegionDataset } from "@/lib/regionContract";
import { boolean, integer, list, matching, nullable, number, object, oneOf, optional, text, type Shape } from "@/lib/shape";
import type { Citation } from "@/lib/types";

export const METRIC_UNITS = ["mm", "cm", "m", "km", "m2", "ha", "g", "kg", "ml", "l"] as const;
export const CONVERSION_BASES = ["DEFINED", "REGIONAL"] as const;
export const GI_STATUSES = ["APPLIED", "REGISTERED", "WITHDRAWN"] as const;
export const CURRENCIES = ["INR", "USD"] as const;
export const PRICE_SCALES = ["THOUSAND", "LAKH", "CRORE"] as const;
export const TREND_VARIABLES = ["annual_precipitation", "annual_mean_temperature"] as const;
export const AMOUNT_KINDS = ["TEMPERATURE", "TIME", "MASS", "LENGTH", "AREA", "VOLUME", "CONCENTRATION", "SHARE", "ACIDITY"] as const;
export const QUANTITY_ROWS_MIN = 3;

export type MeasureRegion = { stateLgd: number; stateName: string; districtLgd: number | null; districtName: string | null };
export type UnitConversion = {
  unit: string;
  metricUnit: (typeof METRIC_UNITS)[number];
  factor: number;
  basis: (typeof CONVERSION_BASES)[number];
  region: MeasureRegion | null;
  citation: Citation | null;
  dataset: RegionDataset | null;
};
export type MetricAmount = { low: number; high: number | null; unit: (typeof METRIC_UNITS)[number] };
export type MeasureRow = {
  stated: string;
  low: number;
  high: number | null;
  unitLabel: string;
  conversion: UnitConversion;
  metric: MetricAmount;
  sentence: ExplainerSentence;
};
export type MeasureBlock = BlockEnvelope<"measure"> & { rows: MeasureRow[] };
export type AmountKind = (typeof AMOUNT_KINDS)[number];
export type QuantityRow = { stated: string; low: number; high: number | null; unit: string; measures: AmountKind; sentence: ExplainerSentence; shownIn?: string };
export type QuantitiesBlock = BlockEnvelope<"quantities"> & { rows: QuantityRow[] };
export type GiStatus = {
  status: (typeof GI_STATUSES)[number];
  applicationNumber: string | null;
  certificateNumber: string | null;
  filedOn: string | null;
  registeredOn: string | null;
  journalIssue: string | null;
  proprietors: string[];
  authorisedUserCount: number | null;
  sentences: ExplainerSentence[];
};
export type PriceRange = {
  stated: string;
  low: number;
  high: number | null;
  currency: (typeof CURRENCIES)[number];
  scale: (typeof PRICE_SCALES)[number] | null;
  per: string | null;
  pricedOn: string;
  place: string;
  districtLgd: number | null;
  sentence: ExplainerSentence;
};
export type MarketGiBlock = BlockEnvelope<"market_gi"> & {
  craft: CraftLink;
  gi: GiStatus | null;
  imitation: ExplainerSentence[];
  prices: PriceRange[];
};
export type ClimateTrend = {
  district: DistrictRef;
  variable: (typeof TREND_VARIABLES)[number];
  datasetCode: string;
  period: string;
  resolution: string;
  mean: number;
  meanUnit: string;
  slopePerDecade: number;
  slopeUnit: string;
  pValue: number;
  significant: boolean;
};
export type GroundwaterValue = {
  district: DistrictRef;
  datasetCode: string;
  variable: string;
  period: string;
  value: number | null;
  valueText: string | null;
  unit: string | null;
  resolution: string;
};
export type ClimateSeries = {
  district: DistrictRef;
  variable: (typeof TREND_VARIABLES)[number];
  datasetCode: string;
  unit: string;
  firstYear: number;
  values: (number | null)[];
};
export type ClimateRiskBlock = BlockEnvelope<"climate_risk"> & {
  trends: ClimateTrend[];
  groundwater: GroundwaterValue[];
  meaning: ExplainerSentence[];
  datasets: RegionDataset[];
  series?: ClimateSeries[];
};

export const PARTIAL_DATE = matching(/^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$/, "a partial date");
const metricUnit = oneOf(METRIC_UNITS);
const unitKey = matching(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/, "a unit key");

const conversionShape: Shape<UnitConversion> = object<UnitConversion>({
  unit: unitKey,
  metricUnit,
  factor: number,
  basis: oneOf(CONVERSION_BASES),
  region: nullable(
    object<MeasureRegion>({ stateLgd: integer, stateName: text, districtLgd: nullable(integer), districtName: nullable(text) })
  ),
  citation: nullable(citationShape),
  dataset: nullable(datasetShape)
});

export const measureBlockShape: Shape<MeasureBlock> = object<MeasureBlock>({
  ...envelope("measure"),
  rows: list(
    object<MeasureRow>({
      stated: text,
      low: number,
      high: nullable(number),
      unitLabel: text,
      conversion: conversionShape,
      metric: object<MetricAmount>({ low: number, high: nullable(number), unit: metricUnit }),
      sentence: explainerSentenceShape
    }),
    1
  )
});

export const quantitiesBlockShape: Shape<QuantitiesBlock> = object<QuantitiesBlock>({
  ...envelope("quantities"),
  rows: list(
    object<QuantityRow>({
      stated: text,
      low: number,
      high: nullable(number),
      unit: unitKey,
      measures: oneOf(AMOUNT_KINDS),
      sentence: explainerSentenceShape,
      shownIn: optional(text)
    }),
    QUANTITY_ROWS_MIN
  )
});

export const marketGiBlockShape: Shape<MarketGiBlock> = object<MarketGiBlock>({
  ...envelope("market_gi"),
  craft: craftLinkShape,
  gi: nullable(
    object<GiStatus>({
      status: oneOf(GI_STATUSES),
      applicationNumber: nullable(text),
      certificateNumber: nullable(text),
      filedOn: nullable(PARTIAL_DATE),
      registeredOn: nullable(PARTIAL_DATE),
      journalIssue: nullable(text),
      proprietors: list(text),
      authorisedUserCount: nullable(integer),
      sentences: list(explainerSentenceShape, 1)
    })
  ),
  imitation: list(explainerSentenceShape),
  prices: list(
    object<PriceRange>({
      stated: text,
      low: number,
      high: nullable(number),
      currency: oneOf(CURRENCIES),
      scale: nullable(oneOf(PRICE_SCALES)),
      per: nullable(text),
      pricedOn: PARTIAL_DATE,
      place: text,
      districtLgd: nullable(integer),
      sentence: explainerSentenceShape
    })
  )
});

export const climateRiskBlockShape: Shape<ClimateRiskBlock> = object<ClimateRiskBlock>({
  ...envelope("climate_risk"),
  trends: list(
    object<ClimateTrend>({
      district: districtShape,
      variable: oneOf(TREND_VARIABLES),
      datasetCode: text,
      period: matching(/^\d{4}-\d{4}$/, "a period of years"),
      resolution: text,
      mean: number,
      meanUnit: text,
      slopePerDecade: number,
      slopeUnit: text,
      pValue: number,
      significant: boolean
    })
  ),
  groundwater: list(
    object<GroundwaterValue>({
      district: districtShape,
      datasetCode: text,
      variable: text,
      period: text,
      value: nullable(number),
      valueText: nullable(text),
      unit: nullable(text),
      resolution: text
    })
  ),
  meaning: list(explainerSentenceShape),
  datasets: list(datasetShape, 1),
  series: optional(
    list(
      object<ClimateSeries>({
        district: districtShape,
        variable: oneOf(TREND_VARIABLES),
        datasetCode: text,
        unit: text,
        firstYear: integer,
        values: list(nullable(number), 1)
      })
    )
  )
});
