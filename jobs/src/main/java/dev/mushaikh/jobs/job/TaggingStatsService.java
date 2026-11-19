package dev.mushaikh.jobs.job;

import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;

import dev.mushaikh.jobs.job.JobDtos.ModelShare;
import dev.mushaikh.jobs.job.JobDtos.TaggingStats;

/**
 * Live tagging cost for the About page, computed from the token counts the worker
 * stores on every tag row and the run totals in ingest_runs.
 *
 * <p>
 * "Actual" is what was really spent (the worker prices free-tier models at $0).
 * "Paid equivalent" prices the same tokens at the reference model's list price, so
 * the page shows what tagging would cost if the free tiers went away. Prices come
 * from {@code app.pricing.*}; keep them in step with worker/pricing.yaml.
 */
@Service
public class TaggingStatsService {

	private static final Duration TTL = Duration.ofMinutes(5);

	/** Rows that carry token counts were tagged by a language model, not the rule-based fallback. */
	private static final String BY_MODEL = """
			select model, count(*) as jobs,
			       coalesce(sum(input_tokens), 0) as input_tokens,
			       coalesce(sum(output_tokens), 0) as output_tokens
			  from job_tags group by model order by jobs desc, model
			""";

	private static final String RUNS = """
			select coalesce(sum(tagged), 0) as tagged, coalesce(sum(llm_cost_usd), 0) as cost,
			       max(finished_at) as last_run
			  from ingest_runs where finished_at is not null
			""";

	private final JdbcClient jdbc;

	private final String referenceModel;

	private final double inputPerMTok;

	private final double outputPerMTok;

	private final double usdToInr;

	private volatile TaggingStats cached;

	private volatile Instant cachedAt = Instant.EPOCH;

	public TaggingStatsService(JdbcClient jdbc, @Value("${app.pricing.reference-model}") String referenceModel,
			@Value("${app.pricing.input-usd-per-mtok}") double inputPerMTok,
			@Value("${app.pricing.output-usd-per-mtok}") double outputPerMTok,
			@Value("${app.pricing.usd-to-inr}") double usdToInr) {
		this.jdbc = jdbc;
		this.referenceModel = referenceModel;
		this.inputPerMTok = inputPerMTok;
		this.outputPerMTok = outputPerMTok;
		this.usdToInr = usdToInr;
	}

	public TaggingStats stats() {
		TaggingStats stats = cached;
		if (stats != null && Instant.now().isBefore(cachedAt.plus(TTL))) {
			return stats;
		}
		stats = compute();
		cached = stats;
		cachedAt = Instant.now();
		return stats;
	}

	public void clearCache() {
		cached = null;
	}

	private record Row(String model, long jobs, long input, long output) {
	}

	private TaggingStats compute() {
		List<Row> rows = jdbc.sql(BY_MODEL)
			.query((rs, n) -> new Row(rs.getString("model"), rs.getLong("jobs"), rs.getLong("input_tokens"),
					rs.getLong("output_tokens")))
			.list();
		long total = rows.stream().mapToLong(Row::jobs).sum();
		List<ModelShare> models = rows.stream()
			.map(r -> new ModelShare(r.model(), r.jobs(), round(100.0 * r.jobs() / Math.max(1, total), 1)))
			.toList();

		List<Row> llm = rows.stream().filter(r -> r.input() + r.output() > 0).toList();
		long llmJobs = llm.stream().mapToLong(Row::jobs).sum();
		long input = llm.stream().mapToLong(Row::input).sum();
		long output = llm.stream().mapToLong(Row::output).sum();

		Double avgIn = null;
		Double avgOut = null;
		Double paidPer1000 = null;
		Double paidTotal = null;
		if (llmJobs > 0) {
			avgIn = round((double) input / llmJobs, 0);
			avgOut = round((double) output / llmJobs, 0);
			paidTotal = usd(input, output);
			paidPer1000 = paidTotal / llmJobs * 1000;
		}

		var runs = jdbc.sql(RUNS).query((rs, n) -> {
			Timestamp ts = rs.getTimestamp("last_run");
			return new Object[] { rs.getLong("tagged"), rs.getDouble("cost"), ts == null ? null : ts.toInstant() };
		}).single();
		long runTagged = (long) runs[0];
		double actualTotal = (double) runs[1];
		Double actualPer1000 = runTagged > 0 ? round(actualTotal / runTagged * 1000, 4) : null;

		return new TaggingStats(total, llmJobs, models, avgIn, avgOut, round(actualTotal, 4), actualPer1000,
				referenceModel, inputPerMTok, outputPerMTok, paidPer1000 == null ? null : round(paidPer1000, 4),
				paidPer1000 == null ? null : round(paidPer1000 * usdToInr, 2),
				paidTotal == null ? null : round(paidTotal, 4), (Instant) runs[2]);
	}

	private double usd(long input, long output) {
		return input * inputPerMTok / 1_000_000 + output * outputPerMTok / 1_000_000;
	}

	private static double round(double value, int places) {
		double f = Math.pow(10, places);
		return Math.round(value * f) / f;
	}
}
