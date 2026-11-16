export type Tags = {
  roleCategory: string;
  roleTitle: string;
  city: string;
  state: string | null;
  workMode: "onsite" | "hybrid" | "remote";
  jobType: "internship" | "full_time" | "contract";
  experienceMin: number | null;
  experienceMax: number | null;
  fresher: boolean;
};

export type JobCard = {
  id: string;
  title: string;
  company: string;
  location: string;
  postedAt: string | null;
  firstSeenAt: string;
  sourceType: string;
  active: boolean;
  tags: Tags | null;
};

export type JobDetail = JobCard & {
  description: string;
  applyUrl: string | null;
};

export type JobPage = {
  items: JobCard[];
  page: number;
  size: number;
  total: number;
  totalPages: number;
};

export type Facet = { value: string; count: number };

export type Meta = {
  activeJobs: number;
  companies: number;
  lastRefresh: string | null;
  roles: Facet[];
  cities: Facet[];
  workModes: Facet[];
  jobTypes: Facet[];
};

export type Me = { authenticated: boolean; email: string | null; name: string | null };

export type UserJob = { job: JobCard; at: string };

export type JobFilters = {
  q?: string;
  role?: string;
  city?: string;
  mode?: string;
  type?: string;
  exp?: string;
  page?: string;
};
