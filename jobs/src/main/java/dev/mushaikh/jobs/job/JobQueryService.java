package dev.mushaikh.jobs.job;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.sql.Types;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;

import dev.mushaikh.jobs.job.JobDtos.Facet;
import dev.mushaikh.jobs.job.JobDtos.JobCard;
import dev.mushaikh.jobs.job.JobDtos.JobDetail;
import dev.mushaikh.jobs.job.JobDtos.JobPage;
import dev.mushaikh.jobs.job.JobDtos.Meta;
import dev.mushaikh.jobs.job.JobDtos.SearchQuery;
import dev.mushaikh.jobs.job.JobDtos.Tags;
import dev.mushaikh.jobs.job.JobDtos.UserJob;

/**
 * Read-only access to the job tables (the Python worker is their only writer).
 * Every statement is a constant string with named parameters; nothing from a
 * request is ever concatenated into SQL.
 */
@Service
public class JobQueryService {

	public static final int PAGE_SIZE = 20;

	private static final String COLUMNS = """
			j.id, j.title, j.company, j.location_raw, j.posted_at, j.first_seen_at, j.is_active,
			s.type as source_type, t.job_id as tag_job_id, t.role_category, t.role_title_clean, t.city,
			t.state, t.work_mode, t.job_type, t.experience_min, t.experience_max, t.is_fresher
			""";

	private static final String JOINS = """
			from jobs j
			join sources s on s.id = j.source_id
			left join job_tags t on t.job_id = j.id
			""";

	/** Listed = active, not a duplicate, and not tagged as non-fresher. */
	private static final String LISTED = "j.is_active and j.canonical_job_id is null and coalesce(t.is_fresher, true)";

	private static final String FILTER = JOINS + " where " + LISTED + """
			 and (cast(:q as text) is null
			      or to_tsvector('english', j.title || ' ' || j.company || ' ' || j.description_text)
			         @@ websearch_to_tsquery('english', cast(:q as text)))
			 and (cast(:role as text) is null or t.role_category = cast(:role as text))
			 and (cast(:city as text) is null or t.city = cast(:city as text))
			 and (cast(:mode as text) is null or t.work_mode = cast(:mode as text))
			 and (cast(:type as text) is null or t.job_type = cast(:type as text))
			 and (cast(:exp as integer) is null or coalesce(t.experience_min, 0) <= cast(:exp as integer))
			""";

	private static final String SEARCH = "select " + COLUMNS + FILTER
			+ " order by coalesce(j.posted_at, j.first_seen_at) desc, j.id limit :limit offset :offset";

	private static final String COUNT = "select count(*) " + FILTER;

	private static final String BY_ID = "select " + COLUMNS + ", j.description_text, j.apply_url " + JOINS
			+ " where j.id = :id";

	private static final String FACET = "select %s as value, count(*) as n " + JOINS + " where " + LISTED
			+ " and t.job_id is not null group by 1 order by n desc, 1";

	private static final Duration META_TTL = Duration.ofSeconds(60);

	private final JdbcClient jdbc;
	private volatile Meta cachedMeta;
	private volatile Instant cachedMetaAt = Instant.EPOCH;

	public JobQueryService(JdbcClient jdbc) {
		this.jdbc = jdbc;
	}

	public JobPage search(SearchQuery query) {
		long total = bind(jdbc.sql(COUNT), query).query(Long.class).single();
		List<JobCard> items = bind(jdbc.sql(SEARCH), query).param("limit", PAGE_SIZE)
			.param("offset", (query.page() - 1) * PAGE_SIZE)
			.query(JobQueryService::card)
			.list();
		int totalPages = (int) Math.max(1, (total + PAGE_SIZE - 1) / PAGE_SIZE);
		return new JobPage(items, query.page(), PAGE_SIZE, total, totalPages);
	}

	private static JdbcClient.StatementSpec bind(JdbcClient.StatementSpec spec, SearchQuery query) {
		return spec.param("q", query.q(), Types.VARCHAR)
			.param("role", query.role(), Types.VARCHAR)
			.param("city", query.city(), Types.VARCHAR)
			.param("mode", query.mode(), Types.VARCHAR)
			.param("type", query.type(), Types.VARCHAR)
			.param("exp", query.exp(), Types.INTEGER);
	}

	public Optional<JobDetail> findById(UUID id) {
		return jdbc.sql(BY_ID).param("id", id).query((rs, n) -> {
			JobCard c = card(rs, n);
			return new JobDetail(c.id(), c.title(), c.company(), c.location(), c.postedAt(), c.firstSeenAt(),
					c.sourceType(), c.active(), c.tags(), TextSafety.plainText(rs.getString("description_text")),
					TextSafety.httpUrlOrNull(rs.getString("apply_url")));
		}).optional();
	}

	public boolean exists(UUID id) {
		return jdbc.sql("select exists(select 1 from jobs where id = :id)").param("id", id).query(Boolean.class).single();
	}

	public Optional<String> applyUrl(UUID id) {
		return jdbc.sql("select apply_url from jobs where id = :id").param("id", id).query(String.class).optional();
	}

	public List<UserJob> savedBy(UUID userId) {
		return jdbc.sql("select " + COLUMNS + ", u.created_at as at " + JOINS
				+ " join saved_jobs u on u.job_id = j.id where u.user_id = :user order by u.created_at desc limit 200")
			.param("user", userId)
			.query((rs, n) -> new UserJob(card(rs, n), instant(rs, "at")))
			.list();
	}

	public List<UserJob> appliedBy(UUID userId) {
		return jdbc.sql("select " + COLUMNS + ", u.at " + JOINS + """
				 join (select job_id, max(clicked_at) as at from apply_clicks
				        where user_id = :user group by job_id) u on u.job_id = j.id
				 order by u.at desc limit 200
				""").param("user", userId).query((rs, n) -> new UserJob(card(rs, n), instant(rs, "at"))).list();
	}

	/** Filter options with counts, plus headline numbers. Cached briefly: it is on every page. */
	public Meta meta() {
		Meta meta = cachedMeta;
		if (meta != null && Instant.now().isBefore(cachedMetaAt.plus(META_TTL))) {
			return meta;
		}
		long active = jdbc.sql("select count(*) " + JOINS + " where " + LISTED).query(Long.class).single();
		long companies = jdbc.sql("select count(distinct lower(j.company)) " + JOINS + " where " + LISTED)
			.query(Long.class)
			.single();
		Instant lastRefresh = jdbc.sql("select max(finished_at) from ingest_runs")
			.query((rs, n) -> Optional.ofNullable(instant(rs, 1)))
			.single()
			.orElse(null);
		meta = new Meta(active, companies, lastRefresh, facet("t.role_category"), facet("t.city"),
				facet("t.work_mode"), facet("t.job_type"));
		cachedMeta = meta;
		cachedMetaAt = Instant.now();
		return meta;
	}

	public void clearMetaCache() {
		cachedMeta = null;
	}

	/** {@code column} is always one of the four literals above, never request input. */
	private List<Facet> facet(String column) {
		return jdbc.sql(FACET.formatted(column))
			.query((rs, n) -> new Facet(rs.getString("value"), rs.getLong("n")))
			.list();
	}

	private static JobCard card(ResultSet rs, int rowNum) throws SQLException {
		Tags tags = null;
		if (rs.getObject("tag_job_id") != null) {
			tags = new Tags(rs.getString("role_category"), rs.getString("role_title_clean"), rs.getString("city"),
					rs.getString("state"), rs.getString("work_mode"), rs.getString("job_type"),
					(Integer) rs.getObject("experience_min"), (Integer) rs.getObject("experience_max"),
					rs.getBoolean("is_fresher"));
		}
		return new JobCard(rs.getObject("id", UUID.class), rs.getString("title"), rs.getString("company"),
				rs.getString("location_raw"), instant(rs, "posted_at"), instant(rs, "first_seen_at"),
				rs.getString("source_type"), rs.getBoolean("is_active"), tags);
	}

	private static Instant instant(ResultSet rs, String column) throws SQLException {
		Timestamp ts = rs.getTimestamp(column);
		return ts == null ? null : ts.toInstant();
	}

	private static Instant instant(ResultSet rs, int column) throws SQLException {
		Timestamp ts = rs.getTimestamp(column);
		return ts == null ? null : ts.toInstant();
	}
}
