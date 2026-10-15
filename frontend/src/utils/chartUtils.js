const getYearTicks = (data, maxTicks = 12) => {
  if (!data.length) return [];

  const step = Math.max(
    1,
    Math.ceil((data.length - 1) / (maxTicks - 1))
  );

  const ticks = data
    .filter((_, index) => index % step === 0)
    .map((item) => item.year);

  const lastYear = data[data.length - 1].year;

  if (!ticks.includes(lastYear)) {
    ticks.push(lastYear);
  }

  return ticks;
};


export { getYearTicks };
