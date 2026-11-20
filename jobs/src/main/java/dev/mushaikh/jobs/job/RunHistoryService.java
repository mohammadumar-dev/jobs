package dev.mushaikh.jobs.job;

import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.List;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;

import dev.mushaikh.jobs.job.JobDtos.RunHistory;
import dev.mushaikh.jobs.job.JobDtos.RunSummary;
import dev.mushaikh.jobs.job.JobDtos.SourceShare;

/**
 * Recent ingest runs and where the listed jobs come from, for the public docs page.
 * Only counts leave the API: error messages stay in ingest_runs.errors_json.
 */
@Service
public class RunHistoryService {

	private static final Duration TTL = Duration.ofMinutes(5);

	private static final int LIMIT = 10;

	private static final String RUNS = """
			select started_at, finished_at, fetched, new, updated, deactivated, tagged, llm_cost_usd,
			       case when jsonb_typeof(errors_json) = 'array' then jsonb_array_length(errors_json) else 0 end
			         as errors
			  from ingest_runs order by started_at desc, id desc limit :limit
			""";

	/** Same definition of "listed" as the job search: active, not a duplicate, open to freshers. */
	private static final String SOURCES = """
			select s.type, count(*) as jobs
			  from jobs j
			  join sources s on s.id = j.source_id
			  left join job_tags t on t.job_id = j.id
			 where j.is_active and j.canonical_job_id is null and coalesce(t.is_fresher, true)
			 group by s.type order by jobs desc, s.type
			""";

	private final JdbcClient jdbc;

	private volatile RunHistory cached;

	private volatile Instant cachedAt = Instant.EPOCH;

	public RunHistoryService(JdbcClient jdbc) {
		this.jdbc = jdbc;
	}

	public RunHistory history() {
		RunHistory history = cached;
		if (history != null && Instant.now().isBefore(cachedAt.plus(TTL))) {
			return history;
		}
		history = new RunHistory(runs(), sources());
		cached = history;
		cachedAt = Instant.now();
		return history;
	}

	public void clearCache() {
		cached = null;
	}

	private List<RunSummary> runs() {
		return jdbc.sql(RUNS).param("limit", LIMIT).query((rs, n) -> {
			Instant started = rs.getTimestamp("started_at").toInstant();
			Timestamp end = rs.getTimestamp("finished_at");
			Instant finished = end == null ? null : end.toInstant();
			Long seconds = finished == null ? null : Duration.between(started, finished).toSeconds();
			return new RunSummary(started, finished, seconds, rs.getInt("fetched"), rs.getInt("new"),
					rs.getInt("updated"), rs.getInt("deactivated"), rs.getInt("tagged"), rs.getInt("errors"),
					rs.getDouble("llm_cost_usd"));
		}).list();
	}

	private List<SourceShare> sources() {
		List<Object[]> rows = jdbc.sql(SOURCES)
			.query((rs, n) -> new Object[] { rs.getString("type"), rs.getLong("jobs") })
			.list();
		long total = rows.stream().mapToLong(r -> (long) r[1]).sum();
		return rows.stream().map(r -> {
			long jobs = (long) r[1];
			return new SourceShare((String) r[0], jobs, Math.round(1000.0 * jobs / Math.max(1, total)) / 10.0);
		}).toList();
	}
}
