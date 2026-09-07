import {readFile, writeFile} from 'node:fs/promises'

const bundlePath = new URL(
  '../src/flask_hypergen/static/hypergen.js',
  import.meta.url,
)
const sourceMapPath = new URL(
  '../src/flask_hypergen/static/hypergen.js.map',
  import.meta.url,
)
const generatedHeader =
  '/*! @generated from src/flask_hypergen/static-src; run tasks/js-build. */\n'
const sourceMapReference = '//# sourceMappingURL=hypergen.js.map'

let bundle = await readFile(bundlePath, 'utf8')
const sourceMapReferences = bundle.match(/\/\/# sourceMappingURL=hypergen\.js\.map/g) || []

if (sourceMapReferences.length === 2) {
  bundle = bundle.replace(
    `\n\n${sourceMapReference}\n`,
    '\n',
  )
} else if (sourceMapReferences.length !== 1) {
  throw new Error(
    `Expected one or two source-map references, found ${sourceMapReferences.length}.`,
  )
}

let sourceMap = JSON.parse(await readFile(sourceMapPath, 'utf8'))
sourceMap.file = 'hypergen.js'

if (!bundle.startsWith(generatedHeader)) {
  bundle = generatedHeader + bundle
  sourceMap.mappings = `;${sourceMap.mappings}`
}

await writeFile(bundlePath, bundle)
await writeFile(sourceMapPath, `${JSON.stringify(sourceMap)}\n`)
