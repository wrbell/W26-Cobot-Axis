// Conventional Commits through @commitlint/config-conventional.
// The preset limits a header to 100 characters.
// Aim for 72 characters or fewer. The lint allows 100.
// A body starts on the line after one blank line.
module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "header-max-length": [2, "always", 100],
    "body-leading-blank": [2, "always"],
  },
};
