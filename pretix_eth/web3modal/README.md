
# Development setup

1. install [nvm](https://github.com/nvm-sh/nvm) the node version manager to ensure you're using the correct version of node
1. with nvm loaded in your current shell, run `nvm use` to automatically switch your active node installation to the project node version
1. `npm install -g yarn`
1. `yarn install`
1. `yarn dev` # run dev server for hot reloading
1. when done developing, run `yarn build` and commit the changes to the dist folder (this subproject's build artifacts are committed to this repo)
