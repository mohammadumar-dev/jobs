package dev.mushaikh.jobs.job;

import java.util.UUID;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.mushaikh.jobs.job.JobDtos.ApplyResponse;
import dev.mushaikh.jobs.job.JobDtos.JobDetail;
import dev.mushaikh.jobs.job.JobDtos.JobPage;
import dev.mushaikh.jobs.job.JobDtos.Meta;
import dev.mushaikh.jobs.job.JobDtos.SearchQuery;
import dev.mushaikh.jobs.security.AppPrincipal;

@RestController
@RequestMapping("/api")
public class JobController {

	/** Filter values are taxonomy labels: letters, digits, spaces, underscore, hyphen. */
	private static final String LABEL = "^[\\p{L}\\p{N} _-]{1,40}$";

	private final JobQueryService jobs;
	private final UserJobService userJobs;

	public JobController(JobQueryService jobs, UserJobService userJobs) {
		this.jobs = jobs;
		this.userJobs = userJobs;
	}

	@GetMapping("/jobs")
	public JobPage search(@RequestParam(required = false) @Size(max = 100) String q,
			@RequestParam(required = false) @Pattern(regexp = LABEL) String role,
			@RequestParam(required = false) @Pattern(regexp = LABEL) String city,
			@RequestParam(required = false) @Pattern(regexp = LABEL) String mode,
			@RequestParam(required = false) @Pattern(regexp = LABEL) String type,
			@RequestParam(required = false) @Min(0) @Max(30) Integer exp,
			@RequestParam(defaultValue = "1") @Min(1) @Max(500) int page) {
		return jobs.search(new SearchQuery(blankToNull(q), blankToNull(role), blankToNull(city), blankToNull(mode),
				blankToNull(type), exp, page));
	}

	@GetMapping("/jobs/{id}")
	public JobDetail detail(@PathVariable UUID id) {
		return jobs.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
	}

	@GetMapping("/meta")
	public Meta meta() {
		return jobs.meta();
	}

	/**
	 * Records the click and returns the source's own apply URL. We cannot apply on the
	 * candidate's behalf; the browser opens this URL in a new tab. Only stored http(s)
	 * URLs are ever returned, so this cannot be used as an open redirect.
	 */
	@PostMapping("/jobs/{id}/apply")
	public ApplyResponse apply(@PathVariable UUID id, @AuthenticationPrincipal AppPrincipal principal) {
		String stored = jobs.applyUrl(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
		String url = TextSafety.httpUrlOrNull(stored);
		if (url == null) {
			throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY);
		}
		userJobs.recordApplyClick(principal == null ? null : principal.id(), id);
		return new ApplyResponse(url);
	}

	private static String blankToNull(String value) {
		return value == null || value.isBlank() ? null : value.strip();
	}
}
