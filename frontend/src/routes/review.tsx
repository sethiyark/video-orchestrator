import { createFileRoute } from "@tanstack/react-router";
import { JobsPage } from "../components/JobsPage";

export const Route = createFileRoute("/review")({ component: Review });

function Review() {
  return (
    <JobsPage
      tab="review"
      heading="Review queue"
      filterJob={(job) => job.status === "awaiting_approval"}
      emptyTitle="Nothing here yet"
      emptyBody="Videos will appear here as they move through the pipeline."
    />
  );
}
