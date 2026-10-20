# Storyboard

The story in one sentence: oil explains why French fuel prices go up and down, taxes explain most
of their level, and a growing refining and retail part explains the trend, while where you fill
up still makes a real difference.

The audience is drivers and households, local journalists and people following the debate on
fuel taxes and rebates. I tried to keep the tone factual and to avoid presenting events as proven
causes.

## Screen 1, Introduction

The opening line is that in September 2026 diesel cost 2.40 € per litre on average, more than at
the 2022 peak. Four figures sit under it: the record, the 2019 average, the 2022 peak and the
jump in Brent between February and April 2026. Then comes a short text on why fuel prices matter,
who the dashboard is for, the questions it answers and the main caveats about the data. There is no
interaction on this screen, it just has to make the reader want to go on.

## Screen 2, Overview

The headline changes with the filters and says how much the chosen fuel has moved since the start
of the selected period. Below it are five figures (latest price, highest and lowest week, cost of
a tank, number of stations), then the weekly price line for each fuel with the events marked by
dotted lines and the 2022 rebate as a shaded area. When a single fuel is selected for the whole
country, a band shows where 80 % of stations priced. The tab ends with the yearly averages and the
weekly stock-outs. The reader can change the fuels, the dates, the regions, the station type and
the measure (price, index or change over a year). The question here is when prices moved and by how
much.

## Screen 3, Oil and the pump price

The headline says that crude oil is only about a quarter of the diesel price and taxes more than
half. The main chart is a stacked area that splits each month into crude, refining and retail,
excise and VAT. Three figures follow on the refining and retail part, then a scatter plot of the
monthly change in crude against the change in the pre-tax price, with one fitted line for months
when crude went up and one for months when it went down, and a bar chart of the correlation at
different lags. This screen answers how much of the price is oil and whether prices rise faster
than they fall.

## Screen 4, Regions

The headline compares the most and least expensive departments over the last four weeks of the
period. The map can show the gap to the national average, the price itself or the change since the
start, and a bar chart next to it ranks the departments at both ends. Below are the motorway extra
cost over time, one small chart per region on the same scale, and a map of a random sample of
stations with the distribution of their prices. The question is where fuel is expensive and how
much the motorway costs.

## Screen 5, Scenarios

Here the reader moves sliders for the Brent price, the refining part, the excise and VAT, enters
their yearly mileage and consumption, and sees the new pump price, their yearly bill and the share
of taxes. Two charts show the price split today and in the scenario, and how the pump price
changes with Brent.

## Screen 6, Data quality

The headline gives the number of raw price updates and the share removed. The screen has the
cleaning steps per year, a chart of how many stations report each week, a table of checks, the
missing values and a paragraph on the limits of the data.

## Screen 7, Conclusion

The findings are computed live from the data and written as short paragraphs, followed by what
they mean for drivers, policy makers and journalists, what could be done next, and a note on
ethics.

## Design choices

Every section starts with a one-sentence headline. Events are dotted lines and the 2022 rebate a
shaded area. Each fuel and each price component always has the same colour, chosen to stay
readable for colour-blind readers. I used small charts per region instead of one chart with
thirteen lines, and every chart has labelled axes with units, a hover tooltip, a written
description and its data table.
