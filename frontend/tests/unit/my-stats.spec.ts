import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { ref } from "vue";

const mockLoadStats = vi.hoisted(() => vi.fn());
const mockUseUserStats = vi.hoisted(() => vi.fn());

vi.mock("@/composables/useUserStats", () => ({
  useUserStats: mockUseUserStats,
}));

vi.mock("lucide-vue-next", () => ({ Trophy: { template: "<span />" } }));

vi.mock("@heroicons/vue/24/outline", () => {
  const s = { template: "<span />" };
  return {
    MapPinIcon: s,
    ExclamationTriangleIcon: s,
    CalendarIcon: s,
    ChartBarIcon: s,
    InformationCircleIcon: s,
    PlayIcon: s,
    CheckCircleIcon: s,
  };
});

import MyStats from "@/pages/userChallenges/MyStats.vue";

const makeStats = (overrides = {}) => ({
  total_caches_found: 100,
  total_challenges: 10,
  active_challenges: 3,
  completed_challenges: 5,
  created_at: "2023-01-15T12:00:00Z",
  first_cache_found_at: null,
  last_cache_found_at: null,
  last_activity_at: null,
  cache_types_stats: [],
  ...overrides,
});

const makeReturn = (overrides = {}) => ({
  stats: ref(null),
  loading: ref(false),
  error: ref<string | null>(null),
  loadStats: mockLoadStats,
  completionRate: ref(0),
  daysSinceLastCache: ref<number | null>(null),
  cachesPerActiveChallenge: ref(0),
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockLoadStats.mockResolvedValue(undefined);
  mockUseUserStats.mockReturnValue(makeReturn());
});

describe("MyStats", () => {
  it("calls loadStats on mount", async () => {
    mount(MyStats, { global: { stubs: { RouterLink: true } } });
    await flushPromises();
    expect(mockLoadStats).toHaveBeenCalledOnce();
  });

  it("shows loading spinner while loading", () => {
    mockUseUserStats.mockReturnValue(makeReturn({ loading: ref(true) }));
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("Chargement");
  });

  it("shows error message when error is set", () => {
    mockUseUserStats.mockReturnValue(
      makeReturn({ error: ref("Erreur réseau") }),
    );
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("Erreur réseau");
  });

  it("renders main stats figures when stats are available", () => {
    mockUseUserStats.mockReturnValue(
      makeReturn({ stats: ref(makeStats()), completionRate: ref(50) }),
    );
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("100"); // total_caches_found
    expect(wrapper.text()).toContain("10"); // total_challenges
    expect(wrapper.text()).toContain("3"); // active_challenges
    expect(wrapper.text()).toContain("5"); // completed_challenges
  });

  it("shows encouragement message when no caches found", () => {
    mockUseUserStats.mockReturnValue(
      makeReturn({ stats: ref(makeStats({ total_caches_found: 0 })) }),
    );
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("Prêt à commencer");
  });

  it("formats created_at date in template", () => {
    mockUseUserStats.mockReturnValue(
      makeReturn({
        stats: ref(makeStats({ created_at: "2023-01-15T00:00:00Z" })),
      }),
    );
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    // fr-FR locale should include "2023" at minimum
    expect(wrapper.text()).toContain("2023");
  });

  it("shows cache types table when cache_types_stats is non-empty", () => {
    const stats = makeStats({
      total_caches_found: 50,
      cache_types_stats: [
        { type_id: "2", type_label: "Traditional", type_code: "T", count: 30 },
      ],
    });
    mockUseUserStats.mockReturnValue(makeReturn({ stats: ref(stats) }));
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("Traditional");
  });

  it("formats first_cache_found_at when present", () => {
    mockUseUserStats.mockReturnValue(
      makeReturn({
        stats: ref(makeStats({ first_cache_found_at: "2022-06-15T00:00:00Z" })),
      }),
    );
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("Première cache trouvée");
    expect(wrapper.text()).toContain("2022");
  });

  it("formats last_activity_at when present", () => {
    mockUseUserStats.mockReturnValue(
      makeReturn({
        stats: ref(makeStats({ last_activity_at: "2023-11-20T00:00:00Z" })),
      }),
    );
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("Dernière activité");
    expect(wrapper.text()).toContain("2023");
  });

  it("shows cachesPerActiveChallenge when active_challenges > 0", () => {
    mockUseUserStats.mockReturnValue(
      makeReturn({
        stats: ref(makeStats({ active_challenges: 2 })),
        cachesPerActiveChallenge: ref(33),
      }),
    );
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("Caches par challenge actif");
  });

  it("shows daysSinceLastCache when last_cache_found_at is set", () => {
    const stats = makeStats({ last_cache_found_at: "2023-06-01T00:00:00Z" });
    mockUseUserStats.mockReturnValue(
      makeReturn({ stats: ref(stats), daysSinceLastCache: ref(42) }),
    );
    const wrapper = mount(MyStats, { global: { stubs: { RouterLink: true } } });
    expect(wrapper.text()).toContain("42");
  });
});
