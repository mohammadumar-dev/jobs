package dev.mushaikh.jobs;

import java.util.TimeZone;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class JobsApplication {

	public static void main(String[] args) {
		// One time zone everywhere. The JDBC driver sends the JVM zone to Postgres, and
		// legacy zone ids (e.g. Asia/Calcutta) are rejected by some Postgres builds.
		TimeZone.setDefault(TimeZone.getTimeZone("UTC"));
		SpringApplication.run(JobsApplication.class, args);
	}

}
