import js from '@eslint/js';

export default [
  {
    ignores: ['dist/**', 'node_modules/**', '**/*.ts', '**/*.tsx'],
  },
  {
    files: ['**/*.js'],
    ...js.configs.recommended,
  },
];
