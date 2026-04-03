import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("@heroicons/vue/24/outline", () => {
  const s = { template: "<span />" };
  return {
    CheckCircleIcon: s,
    XCircleIcon: s,
    ClockIcon: s,
    TrophyIcon: s,
    InformationCircleIcon: s,
    CheckIcon: s,
    XMarkIcon: s,
    ArrowUturnLeftIcon: s,
    ClipboardDocumentListIcon: s,
    ArrowTopRightOnSquareIcon: s,
    FireIcon: s,
  };
});

import UserChallengeCard from "@/components/userChallenges/UserChallengeCard.vue";

type Progress = {
  percent: number | null;
  tasks_done: number | null;
  tasks_total: number | null;
  checked_at: string | null;
};
type Status = "pending" | "accepted" | "dismissed" | "completed";

const makeChallenge = (overrides: Record<string, unknown> = {}) => ({
  id: "uc1",
  status: "pending" as Status,
  computed_status: null,
  effective_status: "pending" as Status,
  progress: null as Progress | null,
  updated_at: null,
  challenge: { id: "c1", name: "Test Challenge" },
  cache: { id: "ca1", GC: "GC12345", difficulty: 2.5, terrain: 2.0 },
  ...overrides,
});

const withProgress = (percent: number): Progress => ({
  percent,
  tasks_done: null,
  tasks_total: null,
  checked_at: null,
});

describe("progress percent badge", () => {
  it("shows percent badge in header when accepted and progress.percent is set", () => {
    const wrapper = mount(UserChallengeCard, {
      props: {
        challenge: makeChallenge({
          status: "accepted",
          progress: {
            percent: 75,
            tasks_done: null,
            tasks_total: null,
            checked_at: null,
          },
        }),
      },
    });
    expect(wrapper.find("h3").text()).toContain("75%");
  });

  it("does not show percent badge when status is pending", () => {
    const wrapper = mount(UserChallengeCard, {
      props: {
        challenge: makeChallenge({
          status: "pending",
          progress: {
            percent: 75,
            tasks_done: null,
            tasks_total: null,
            checked_at: null,
          },
        }),
      },
    });
    // The span with text-gray-600 font-semibold text-sm badge should not appear
    expect(wrapper.find("h3").html()).not.toContain(
      "text-sm font-semibold text-gray-600",
    );
  });
});

describe("progressBarStyle", () => {
  it("shows gradient bar and clip-path when progress < 100%", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ progress: withProgress(50) }) },
    });
    expect(wrapper.html()).toContain("clip-path");
  });

  it("shows solid green bar at exactly 100%", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ progress: withProgress(100) }) },
    });
    const bar = wrapper.find(".h-full");
    expect(bar.attributes("style")).toContain("rgb(34, 197, 94)");
    expect(bar.attributes("style")).not.toContain("clip-path");
  });

  it("clips to 100% when progress exceeds 100", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ progress: withProgress(150) }) },
    });
    const bar = wrapper.find(".h-full");
    expect(bar.attributes("style")).toContain("rgb(34, 197, 94)");
  });

  it('shows "Pas encore commencé" when progress is null', () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ progress: null }) },
    });
    expect(wrapper.text()).toContain("Pas encore commencé");
  });
});

describe("status icons", () => {
  it("shows green icon for accepted status", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "accepted" }) },
    });
    expect(wrapper.find("h3").html()).toContain("text-green-600");
  });

  it("shows red icon for dismissed status", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "dismissed" }) },
    });
    expect(wrapper.find("h3").html()).toContain("text-red-600");
  });

  it("shows gray icon for pending status with no computed completion", () => {
    const wrapper = mount(UserChallengeCard, {
      props: {
        challenge: makeChallenge({ status: "pending", computed_status: null }),
      },
    });
    expect(wrapper.find("h3").html()).toContain("text-gray-600");
    expect(wrapper.find("h3").html()).not.toContain("text-green-600");
    expect(wrapper.find("h3").html()).not.toContain("text-red-600");
    expect(wrapper.find("h3").html()).not.toContain("text-gold-600");
  });

  it("shows trophy icon for completed status", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "completed" }) },
    });
    expect(wrapper.find("h3").html()).toContain("text-gold-600");
  });

  it("shows trophy icon when computed_status is completed", () => {
    const wrapper = mount(UserChallengeCard, {
      props: {
        challenge: makeChallenge({
          status: "pending",
          computed_status: "completed",
        }),
      },
    });
    expect(wrapper.find("h3").html()).toContain("text-gold-600");
  });
});

describe("button visibility", () => {
  it("hides accept button when status is accepted", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "accepted" }) },
    });
    expect(wrapper.find('[title="Accepter"]').exists()).toBe(false);
  });

  it("shows reset button when status is accepted", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "accepted" }) },
    });
    expect(wrapper.find('[title="Réinitialiser (pending)"]').exists()).toBe(
      true,
    );
  });

  it("shows tasks button when status is accepted", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "accepted" }) },
    });
    expect(wrapper.find('[title="Tâches"]').exists()).toBe(true);
  });

  it("hides dismiss button when status is dismissed", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "dismissed" }) },
    });
    expect(wrapper.find('[title="Ignorer"]').exists()).toBe(false);
  });

  it("shows reset button when status is dismissed", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "dismissed" }) },
    });
    expect(wrapper.find('[title="Réinitialiser (pending)"]').exists()).toBe(
      true,
    );
  });

  it("hides accept and dismiss but shows tasks when computed_status is completed", () => {
    const wrapper = mount(UserChallengeCard, {
      props: {
        challenge: makeChallenge({
          status: "pending",
          computed_status: "completed",
        }),
      },
    });
    expect(wrapper.find('[title="Accepter"]').exists()).toBe(false);
    expect(wrapper.find('[title="Ignorer"]').exists()).toBe(false);
    expect(wrapper.find('[title="Tâches"]').exists()).toBe(true);
  });

  it("hides reset button for pending status", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: makeChallenge({ status: "pending" }) },
    });
    expect(wrapper.find('[title="Réinitialiser (pending)"]').exists()).toBe(
      false,
    );
  });

  it("hides tasks button for pending status without computed completion", () => {
    const wrapper = mount(UserChallengeCard, {
      props: {
        challenge: makeChallenge({ status: "pending", computed_status: null }),
      },
    });
    expect(wrapper.find('[title="Tâches"]').exists()).toBe(false);
  });
});

describe("difficultyColor", () => {
  const withDifficulty = (difficulty: unknown) =>
    makeChallenge({ cache: { id: "ca1", GC: "GC1", difficulty, terrain: 2 } });

  it("returns text-green-500 for difficulty 1 (≤ 1.5)", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: withDifficulty(1) },
    });
    expect(wrapper.html()).toContain("text-green-500");
  });

  it("returns text-yellow-500 for difficulty 2 (≤ 2.5)", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: withDifficulty(2) },
    });
    expect(wrapper.html()).toContain("text-yellow-500");
  });

  it("returns text-orange-500 for difficulty 3 (≤ 3.5)", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: withDifficulty(3) },
    });
    expect(wrapper.html()).toContain("text-orange-500");
  });

  it("returns text-red-500 for difficulty 4 (≤ 4.5)", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: withDifficulty(4) },
    });
    expect(wrapper.html()).toContain("text-red-500");
  });

  it("returns text-purple-600 for difficulty 5 (> 4.5)", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: withDifficulty(5) },
    });
    expect(wrapper.html()).toContain("text-purple-600");
  });

  it("returns text-gray-400 for non-numeric difficulty string", () => {
    const wrapper = mount(UserChallengeCard, {
      props: { challenge: withDifficulty("bad") },
    });
    expect(wrapper.html()).toContain("text-gray-400");
  });
});
