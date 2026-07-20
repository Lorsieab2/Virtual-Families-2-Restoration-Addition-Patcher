const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { PNG } = require("pngjs");

const root = path.resolve(__dirname, "..");
const sourceDir = path.join(root, "work", "vf2_apk_extract", "renovations");
const destinationDir = path.join(root, "work", "assets", "mobile_renovations");
const outputDir = path.join(root, "outputs");

const expectedNames = [
  "tp233_sw_bathroom_black.png",
  "tp233_sw_bathroom_blue_marble.png",
  "tp234_sw_bathroom_brown.png",
  "tp234_sw_bathroom_green.png",
  "tp235_sw_bathroom_pink.png",
  "tp238_beige_kitchen.png",
  "tp238_beige_workshop.png",
  "tp239_red_office.png",
  "tp239_yellow_kitchen.png",
  "tp240_country_kitchen.png",
  "tp240_dark_office.png",
  "tp241_green_office.png",
  "tp241_modern_office.png",
  "tp242_blue_office.png",
  "tp242_checkered_workshop.png",
].sort();

function sha256(filePath) {
  return crypto
    .createHash("sha256")
    .update(fs.readFileSync(filePath))
    .digest("hex")
    .toUpperCase();
}

function assertExactVerticalFlip(sourcePixels, outputPixels, name) {
  const sourceInfo = sourcePixels.info;
  const outputInfo = outputPixels.info;
  if (
    sourceInfo.width !== outputInfo.width ||
    sourceInfo.height !== outputInfo.height ||
    sourceInfo.channels !== 4 ||
    outputInfo.channels !== 4
  ) {
    throw new Error(
      `Geometry/channel mismatch for ${name}: ${JSON.stringify(sourceInfo)} vs ${JSON.stringify(outputInfo)}`,
    );
  }

  const rowBytes = sourceInfo.width * 4;
  for (let y = 0; y < sourceInfo.height; y += 1) {
    const sourceStart = (sourceInfo.height - 1 - y) * rowBytes;
    const outputStart = y * rowBytes;
    const sourceRow = sourcePixels.data.subarray(sourceStart, sourceStart + rowBytes);
    const outputRow = outputPixels.data.subarray(outputStart, outputStart + rowBytes);
    if (!sourceRow.equals(outputRow)) {
      throw new Error(`Pixel mismatch for ${name} at output row ${y}`);
    }
  }
}

function escapeXml(value) {
  const replacements = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&apos;",
  };
  return value.replace(/[&<>"']/g, (character) => replacements[character]);
}

function decodedRgba(filePath) {
  const png = PNG.sync.read(fs.readFileSync(filePath), { skipRescale: true });
  return {
    data: png.data,
    info: { width: png.width, height: png.height, channels: 4 },
  };
}

async function writeCorrectedFiles(tempDir) {
  const records = [];
  for (const name of expectedNames) {
    const sourcePath = path.join(sourceDir, name);
    const tempPath = path.join(tempDir, name);
    const sourcePixels = decodedRgba(sourcePath);
    const { width, height } = sourcePixels.info;
    const rowBytes = width * 4;
    const flipped = Buffer.allocUnsafe(sourcePixels.data.length);

    for (let y = 0; y < height; y += 1) {
      const sourceStart = (height - 1 - y) * rowBytes;
      sourcePixels.data.copy(
        flipped,
        y * rowBytes,
        sourceStart,
        sourceStart + rowBytes,
      );
    }

    fs.writeFileSync(
      tempPath,
      PNG.sync.write(
        { width, height, data: flipped },
        {
          colorType: 6,
          deflateLevel: 9,
          inputColorType: 6,
          inputHasAlpha: true,
        },
      ),
    );

    const tempPixels = decodedRgba(tempPath);
    assertExactVerticalFlip(sourcePixels, tempPixels, name);
    records.push({
      name,
      width,
      height,
      sourceSha256: sha256(sourcePath),
      outputSha256: sha256(tempPath),
      relation: "exact vertical pixel flip",
    });
  }
  return records;
}

async function createContactSheet(records) {
  const columns = 3;
  const padding = 16;
  const contentWidth = Math.max(...records.map((record) => record.width));
  const contentHeight = Math.max(...records.map((record) => record.height));
  const tileWidth = contentWidth + padding * 2;
  const tileHeight = contentHeight + padding * 2;
  const rows = Math.ceil(records.length / columns);
  const sheetWidth = columns * tileWidth;
  const sheetHeight = rows * tileHeight;
  const sheet = new PNG({ width: sheetWidth, height: sheetHeight });

  for (let y = 0; y < sheetHeight; y += 1) {
    for (let x = 0; x < sheetWidth; x += 1) {
      const index = (y * sheetWidth + x) * 4;
      const light = (Math.floor(x / 16) + Math.floor(y / 16)) % 2 === 0;
      const value = light ? 232 : 207;
      sheet.data[index] = value;
      sheet.data[index + 1] = light ? 237 : 215;
      sheet.data[index + 2] = light ? 242 : 223;
      sheet.data[index + 3] = 255;
    }
  }

  for (let index = 0; index < records.length; index += 1) {
    const record = records[index];
    const source = decodedRgba(path.join(destinationDir, record.name));
    const left =
      (index % columns) * tileWidth +
      padding +
      Math.floor((contentWidth - record.width) / 2);
    const top =
      Math.floor(index / columns) * tileHeight +
      padding +
      Math.floor((contentHeight - record.height) / 2);
    for (let y = 0; y < record.height; y += 1) {
      for (let x = 0; x < record.width; x += 1) {
        const sourceIndex = (y * record.width + x) * 4;
        const destinationIndex = ((top + y) * sheetWidth + left + x) * 4;
        const alpha = source.data[sourceIndex + 3] / 255;
        const inverseAlpha = 1 - alpha;
        sheet.data[destinationIndex] = Math.round(
          source.data[sourceIndex] * alpha +
            sheet.data[destinationIndex] * inverseAlpha,
        );
        sheet.data[destinationIndex + 1] = Math.round(
          source.data[sourceIndex + 1] * alpha +
            sheet.data[destinationIndex + 1] * inverseAlpha,
        );
        sheet.data[destinationIndex + 2] = Math.round(
          source.data[sourceIndex + 2] * alpha +
            sheet.data[destinationIndex + 2] * inverseAlpha,
        );
        sheet.data[destinationIndex + 3] = 255;
      }
    }
  }

  fs.mkdirSync(outputDir, { recursive: true });
  const contactSheet = path.join(
    outputDir,
    "b156-mobile-renovations-upright-contact-sheet.png",
  );
  fs.writeFileSync(
    contactSheet,
    PNG.sync.write(sheet, {
      colorType: 6,
      deflateLevel: 9,
      inputColorType: 6,
      inputHasAlpha: true,
    }),
  );
  return contactSheet;
}

async function main() {
  const currentNames = fs
    .readdirSync(destinationDir)
    .filter((name) => name.toLowerCase().endsWith(".png"))
    .sort();
  if (JSON.stringify(currentNames) !== JSON.stringify(expectedNames)) {
    throw new Error(`Curated set mismatch: ${JSON.stringify(currentNames)}`);
  }

  for (const name of expectedNames) {
    const sourcePath = path.join(sourceDir, name);
    const destinationPath = path.join(destinationDir, name);
    if (!fs.existsSync(sourcePath)) {
      throw new Error(`Missing source: ${sourcePath}`);
    }
    if (sha256(sourcePath) !== sha256(destinationPath)) {
      const sourcePixels = decodedRgba(sourcePath);
      const destinationPixels = decodedRgba(destinationPath);
      assertExactVerticalFlip(sourcePixels, destinationPixels, name);
    }
  }

  const tempDir = path.join(
    destinationDir,
    `._upright_${process.pid}_${Date.now()}`,
  );
  fs.mkdirSync(tempDir);
  const records = await writeCorrectedFiles(tempDir);

  for (const record of records) {
    fs.copyFileSync(
      path.join(tempDir, record.name),
      path.join(destinationDir, record.name),
    );
  }

  for (const record of records) {
    const sourcePixels = decodedRgba(path.join(sourceDir, record.name));
    const destinationPixels = decodedRgba(
      path.join(destinationDir, record.name),
    );
    assertExactVerticalFlip(sourcePixels, destinationPixels, record.name);
    if (sha256(path.join(destinationDir, record.name)) !== record.outputSha256) {
      throw new Error(`Post-copy hash mismatch: ${record.name}`);
    }
    fs.unlinkSync(path.join(tempDir, record.name));
  }
  fs.rmdirSync(tempDir);

  const contactSheet = await createContactSheet(records);
  const qaManifest = path.join(
    outputDir,
    "b156-mobile-renovations-upright-qa.json",
  );
  fs.writeFileSync(
    qaManifest,
    `${JSON.stringify(
      {
        sourceDir,
        destinationDir,
        count: records.length,
        verification:
          "Every decoded RGBA output row equals the corresponding reversed source row.",
        files: records,
      },
      null,
      2,
    )}\n`,
  );

  console.log(`FLIPPED=${records.length}`);
  console.log(`CONTACT_SHEET=${contactSheet}`);
  console.log(`QA_MANIFEST=${qaManifest}`);
  for (const record of records) {
    console.log(
      `${record.name} ${record.width}x${record.height} ${record.outputSha256}`,
    );
  }
}

main().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
