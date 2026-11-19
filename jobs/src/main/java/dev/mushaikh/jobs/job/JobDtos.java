package dev.mushaikh.jobs.job;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public final class JobDtos {

	private JobDtos() {
	}

	/** Null when the job has not been tagged yet. */
	public record Tags(String roleCategory, String roleTitle, String city, String state, String workMode,
			String jobType, Integer experienceMin, Integer experienceMax, boolean fresher) {
	}

	public record JobCard(UUID id, String title, String company, String location, Instant postedAt,
			Instant firstSeenAt, String sourceType, boolean active, Tags tags) {
	}

	public record JobDetail(UUID id, String title, String company, String location, Instant postedAt,
			Instant firstSeenAt, String sourceType, boolean active, Tags tags, String description, String applyUrl) {
	}

	public record JobPage(List<JobCard> items, int page, int size, long total, int totalPages) {
	}

	public record Facet(String value, long count) {
	}

	public record Meta(long activeJobs, long companies, Instant lastRefresh, List<Facet> roles, List<Facet> cities,
			List<Facet> workModes, List<Facet> jobTypes) {
	}

	/** Share of tagged jobs per model ("heuristic-v1" is the rule-based fallback). */
	public record ModelShare(String model, long jobs, double percent) {
	}

	/**
	 * Tagging cost from stored token counts. {@code actual*} is what was spent (free
	 * tiers are $0); {@code paid*} prices the same tokens at {@code referenceModel}.
	 * Nullable numbers are null until there is data.
	 */
	public record TaggingStats(long jobsTagged, long llmTaggedJobs, List<ModelShare> models, Double avgInputTokens,
			Double avgOutputTokens, double actualCostUsd, Double actualPer1000Usd, String referenceModel,
			double referenceInputUsdPerMTok, double referenceOutputUsdPerMTok, Double paidPer1000Usd,
			Double paidPer1000Inr, Double paidTotalUsd, Instant lastRun) {
	}

	/** A saved or applied job with when the user did it. */
	public record UserJob(JobCard job, Instant at) {
	}

	public record ApplyResponse(String applyUrl) {
	}

	public record SearchQuery(String q, String role, String city, String mode, String type, Integer exp, int page) {
	}
}
