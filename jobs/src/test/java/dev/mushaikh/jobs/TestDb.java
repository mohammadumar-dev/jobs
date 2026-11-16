package dev.mushaikh.jobs;

import java.io.IOException;
import java.io.UncheckedIOException;

import javax.sql.DataSource;

import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

/** One real (embedded) PostgreSQL for the whole test run; Flyway migrates it. No Docker needed. */
@TestConfiguration(proxyBeanMethods = false)
public class TestDb {

	private static EmbeddedPostgres postgres;

	private static synchronized EmbeddedPostgres postgres() {
		if (postgres == null) {
			try {
				postgres = EmbeddedPostgres.builder().start();
			}
			catch (IOException ex) {
				throw new UncheckedIOException(ex);
			}
		}
		return postgres;
	}

	@Bean
	@Primary
	DataSource dataSource() {
		return postgres().getPostgresDatabase();
	}
}
