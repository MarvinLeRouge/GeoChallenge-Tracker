<template>
  <div class="relative inline-block text-left">
    <button
      data-testid="dropdown-toggle"
      type="button"
      class="border border-gray-200 rounded px-2 py-1 text-xs text-gray-700 bg-white dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
      @click="open = !open"
    >
      {{ label }}
    </button>
    <div
      v-if="open"
      data-testid="dropdown-panel"
      class="absolute z-30 mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 p-2 dark:bg-gray-900 dark:border-gray-700"
    >
      <label
        v-for="opt in options"
        :key="opt.code"
        class="flex items-center gap-2 px-1 py-1 text-xs text-gray-700 dark:text-gray-300"
      >
        <input
          type="checkbox"
          :checked="modelValue.includes(opt.code)"
          @change="
            toggle(opt.code, ($event.target as HTMLInputElement).checked)
          "
        />
        <span>{{ opt.name }}</span>
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";

interface TypeOption {
  code: string;
  name: string;
}

const props = defineProps<{
  options: TypeOption[];
  modelValue: string[];
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: string[]): void;
}>();

const open = ref(false);

const label = computed(() =>
  props.modelValue.length > 0
    ? `Types (${props.modelValue.length})`
    : "Tous les types",
);

function toggle(code: string, checked: boolean) {
  const next = checked
    ? [...props.modelValue, code]
    : props.modelValue.filter((c) => c !== code);
  emit("update:modelValue", next);
}
</script>
