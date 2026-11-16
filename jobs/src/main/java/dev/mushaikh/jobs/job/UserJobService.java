package dev.mushaikh.jobs.job;

import java.sql.Types;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;

/** Writes to the user-owned tables saved_jobs and apply_clicks. */
@Service
public class UserJobService {

	private final JdbcClient jdbc;

	public UserJobService(JdbcClient jdbc) {
		this.jdbc = jdbc;
	}

	public void save(UUID userId, UUID jobId) {
		jdbc.sql("insert into saved_jobs (user_id, job_id) values (:user, :job) on conflict do nothing")
			.param("user", userId)
			.param("job", jobId)
			.update();
	}

	public void unsave(UUID userId, UUID jobId) {
		jdbc.sql("delete from saved_jobs where user_id = :user and job_id = :job")
			.param("user", userId)
			.param("job", jobId)
			.update();
	}

	public void recordApplyClick(UUID userIdOrNull, UUID jobId) {
		jdbc.sql("insert into apply_clicks (user_id, job_id) values (:user, :job)")
			.param("user", userIdOrNull, Types.OTHER)
			.param("job", jobId)
			.update();
	}
}
