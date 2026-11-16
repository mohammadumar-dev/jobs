package dev.mushaikh.jobs.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app")
public record AppProperties(String publicOrigin, String proxySecret, Security security, SessionCookie sessionCookie, RateLimit rateLimit,
		Lockout lockout) {

	public record SessionCookie(String name, boolean secure, Duration maxAge) {
	}

	public record Security(boolean requireHttps) {
	}

	public record RateLimit(int authPerMinute, int searchPerMinute) {
	}

	public record Lockout(int maxFailures, Duration duration) {
	}
}
