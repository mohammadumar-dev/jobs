package dev.mushaikh.jobs.job;

import java.util.List;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.mushaikh.jobs.job.JobDtos.UserJob;
import dev.mushaikh.jobs.security.AppPrincipal;

/** Everything here requires a signed-in user (enforced in SecurityConfig). */
@RestController
@RequestMapping("/api")
public class UserJobController {

	private final JobQueryService jobs;
	private final UserJobService userJobs;

	public UserJobController(JobQueryService jobs, UserJobService userJobs) {
		this.jobs = jobs;
		this.userJobs = userJobs;
	}

	@PostMapping("/jobs/{id}/save")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void save(@PathVariable UUID id, @AuthenticationPrincipal AppPrincipal principal) {
		if (!jobs.exists(id)) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND);
		}
		userJobs.save(principal.id(), id);
	}

	@DeleteMapping("/jobs/{id}/save")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void unsave(@PathVariable UUID id, @AuthenticationPrincipal AppPrincipal principal) {
		userJobs.unsave(principal.id(), id);
	}

	@GetMapping("/me/saved")
	public List<UserJob> saved(@AuthenticationPrincipal AppPrincipal principal) {
		return jobs.savedBy(principal.id());
	}

	@GetMapping("/me/applied")
	public List<UserJob> applied(@AuthenticationPrincipal AppPrincipal principal) {
		return jobs.appliedBy(principal.id());
	}
}
