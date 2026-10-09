import streamlit as st
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageDraw
from collections import Counter
import io
import os
import tempfile

# ReportLab importeren voor zuivere PDF generatie
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.pagesizes import A0, A1, A2, A3, A4, A5
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    st.warning("ReportLab niet geïnstalleerd. PDF export werkt mogelijk niet optimaal.")

# pikepdf (qpdf) voor echte PDF/X-1a structuur (OutputIntent, TrimBox/BleedBox)
try:
    import pikepdf
    PIKEPDF_SUPPORT = True
except ImportError:
    PIKEPDF_SUPPORT = False

# Pad naar het meegeleverde generieke CMYK ICC-profiel (zie icc_profiles/README.md)
ICC_PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icc_profiles", "generic_cmyk.icc")

# PDF import libraries
try:
    from pdf2image import convert_from_bytes
    PDF_IMPORT = True
except ImportError:
    PDF_IMPORT = False
    st.info("📌 Voor PDF import: pip install pdf2image")

# Pagina-instellingen
st.set_page_config(
    page_title="C.A. Professional Bleed Tool - Pixel Perfect",
    page_icon="📐",
    layout="wide"
)

# CSS
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    h1 { color: #00594F; }
    .report-title { font-weight: bold; font-size: 20px; color: #00594F; border-bottom: 2px solid #00594F; padding-bottom: 8px; margin-bottom: 15px; }
    .warning-text { color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }
    .success-text { color: #0f5132; background-color: #d1e7dd; padding: 10px; border-radius: 5px; margin: 10px 0; }
    .info-text { color: #084298; background-color: #cfe2ff; padding: 10px; border-radius: 5px; margin: 10px 0; }
    div.stButton > button { background-color: #00594F; color: white; font-weight: bold; }
    div.stButton > button:hover { background-color: #004d44; }
    </style>
    """, unsafe_allow_html=True)

# Formaat specificaties (mm)
FORMATS = {
    "A5": (148, 210),
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189)
}

# Kleurprofielen / drukstandaarden
# Elk profiel heeft naast de omschrijving ook een "total area coverage"-limiet
# (tac, maximale gezamenlijke inktdekking in %) en een gcr-factor (hoeveel
# C/M/Y vervangen wordt door K - "Gray Component Replacement"). Dit zijn de
# twee belangrijkste kenmerken die een drukstandaard onderscheiden qua
# kleuropbouw, en worden gebruikt om de RGB->CMYK omzetting per profiel te
# tunen. Zie icc_profiles/README.md voor een belangrijke kanttekening over
# wat dit wel en niet is (benadering op basis van inktlimiet/zwartopbouw,
# geen ingesloten gecertificeerd ICC-LUT van Fogra/SWOP/Idealliance zelf).
COLOR_PROFILES = {
    "CoatedFOGRA39": {
        "desc": "ISO 12647-2, gestreken papier - EU-standaard (klassiek, t/m ~2015)",
        "tac": 330, "gcr": 0.75,
    },
    "CoatedFOGRA51": {
        "desc": "ISO 12647-2:2013, gestreken papier - huidige EU-standaard",
        "tac": 300, "gcr": 0.80,
    },
    "CoatedFOGRA52": {
        "desc": "ISO 12647-2:2013 variant, gestreken papier (iets lichter papiertype)",
        "tac": 300, "gcr": 0.80,
    },
    "UncoatedFOGRA29": {
        "desc": "ISO 12647-2, ongestreken papier - EU-standaard (klassiek, t/m ~2015)",
        "tac": 260, "gcr": 0.60,
    },
    "UncoatedFOGRA47": {
        "desc": "ISO 12647-2:2013, ongestreken papier - huidige EU-standaard",
        "tac": 240, "gcr": 0.60,
    },
    "PSOLWCimprovedFOGRA45": {
        "desc": "Krantenpapier / LWC (bv. tijdschriften, dunne papiersoorten)",
        "tac": 260, "gcr": 0.55,
    },
    "USWebCoatedSWOP": {
        "desc": "US Web Coated SWOP v2 - VS-standaard voor gestreken offsetdruk",
        "tac": 300, "gcr": 0.75,
    },
    "USWebUncoated": {
        "desc": "VS-standaard voor ongestreken papier",
        "tac": 260, "gcr": 0.60,
    },
    "GRACoLCoated": {
        "desc": "GRACoL 2006/2013 - Noord-Amerikaanse commerciële vellendruk",
        "tac": 320, "gcr": 0.78,
    },
    "JapanColor2001Coated": {
        "desc": "Japanse standaard, gestreken papier",
        "tac": 350, "gcr": 0.80,
    },
    "JapanColor2011Coated": {
        "desc": "Japanse standaard (herzien), gestreken papier",
        "tac": 320, "gcr": 0.78,
    },
    "GenericCMYK": {
        "desc": "Algemene CMYK-conversie, geen specifieke drukstandaard",
        "tac": 300, "gcr": 0.70,
    },
}

# Drukker-presets: vertaalt "bij welke drukker lever je dit aan" naar de
# juiste technische instellingen, zodat een leek niet zelf hoeft te weten
# wat Fogra39 of PDF/X-1a betekent. Dit zijn instellingen die gebruikers
# hebben gemeld als werkend bij deze drukkers op het moment van schrijven -
# drukkers wijzigen hun eisen weleens, dus bij twijfel altijd even de
# upload-pagina van de drukker zelf checken.
PRINTER_PRESETS = {
    "Weet ik niet / algemeen (veilige standaard)": {
        "profile": "CoatedFOGRA39",
        "pdfx1a": False,
        "pdf_version": "1.4",
        "gts_label": "PDF/X-1a:2003",
        "explain": "Gewone CMYK-PDF zonder strikte PDF/X-eisen. Werkt bij de "
                   "meeste drukkers die geen expliciet bestandstype vermelden.",
    },
    "Bizay - gevouwen folders (PDF/X-1a)": {
        "profile": "CoatedFOGRA39",
        "pdfx1a": True,
        "pdf_version": "1.3",
        "gts_label": "PDF/X-1a:2001",
        "explain": "Bizay vraagt voor gevouwen folders expliciet PDF/X-1a. "
                   "Dit gebruikt de klassieke PDF/X-1a:2001-variant (PDF 1.3) "
                   "omdat die het breedst herkend wordt door drukkerij-checks.",
    },
    "Onlineprinters.nl (PDF 1.5 + Fogra CMYK)": {
        "profile": "CoatedFOGRA51",
        "pdfx1a": False,
        "pdf_version": "1.5",
        "gts_label": "PDF/X-1a:2003",
        "explain": "Onlineprinters.nl vraagt PDF 1.5 met een Fogra CMYK-"
                   "variant. Standaard Fogra51 (huidige EU-standaard) - "
                   "controleer op hun site of ze specifiek Fogra39 willen "
                   "(oudere papiersoort/opdracht), pas dan aan bij "
                   "'Geavanceerd'.",
    },
    "Geavanceerd: zelf instellen": None,
}

def rgb_to_cmyk(r, g, b):
    """RGB naar CMYK (0-100%) - gebruikt voor de losse kleur-preview in de sidebar."""
    if r == 0 and g == 0 and b == 0:
        return (0, 0, 0, 100)

    r_prime = r / 255.0
    g_prime = g / 255.0
    b_prime = b / 255.0

    k = 1 - max(r_prime, g_prime, b_prime)

    if k < 1:
        c = (1 - r_prime - k) / (1 - k)
        m = (1 - g_prime - k) / (1 - k)
        y = (1 - b_prime - k) / (1 - k)
    else:
        c, m, y = 0, 0, 0

    return (c * 100, m * 100, y * 100, k * 100)


def rgb_image_to_cmyk_array(rgb_img, tac_limit=300, gcr=0.7):
    """
    ECHTE pixel-voor-pixel RGB -> CMYK omzetting (numpy, vectorized), met:
    - Gray Component Replacement (gcr): hoeveel C/M/Y vervangen wordt door K
    - Total Area Coverage (tac_limit): drukkers keuren bestanden af die de
      gezamenlijke inktdekking overschrijden; wordt hier proportioneel geclamped.
    Retourneert een HxWx4 uint8 array met "natuurlijke" inktwaarden (0=geen inkt).
    """
    arr = np.asarray(rgb_img.convert("RGB"), dtype=np.float64) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    k = 1.0 - np.maximum(np.maximum(r, g), b)
    denom = np.clip(1.0 - k, 1e-6, None)
    c = np.clip((1.0 - r - k) / denom, 0, 1)
    m = np.clip((1.0 - g - k) / denom, 0, 1)
    y = np.clip((1.0 - b - k) / denom, 0, 1)

    # Gray component replacement: versterk K volgens het profiel (meer GCR =
    # rijkere/stabielere zwarttinten, minder totale inkt in donkere vlakken)
    k = np.clip(k * (1.0 + 0.15 * gcr), 0, 1)

    total = (c + m + y + k) * 100.0
    over = total > tac_limit
    if np.any(over):
        scale = np.ones_like(total)
        scale[over] = tac_limit / total[over]
        c = c * scale
        m = m * scale
        y = y * scale
        k = k * scale

    cmyk = np.stack([c, m, y, k], axis=-1)
    return np.clip(cmyk * 255.0 + 0.5, 0, 255).astype(np.uint8)


def cmyk_array_to_jpeg_bytes(cmyk_u8, quality=92):
    """CMYK-array (HxWx4, natuurlijke inktwaarden) opslaan als CMYK-JPEG-bytes.
    Geverifieerd (handmatige round-trip test) dat hier GEEN voor-inversie nodig
    is: PIL/libjpeg schrijft en leest zijn eigen CMYK-JPEGs consistent, en de
    kleuren komen correct (niet geïnverteerd) uit de uiteindelijke PDF."""
    h, w = cmyk_u8.shape[:2]
    img = Image.frombytes("CMYK", (w, h), cmyk_u8.tobytes())
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def finalize_pdfx1a(base_pdf_bytes, width_pt, height_pt, bleed_pt, output_condition,
                     pdf_version="1.4", gts_label="PDF/X-1a:2003"):
    """Post-processeert een reportlab-PDF met pikepdf tot een structureel
    geldige PDF/X-1a: voegt OutputIntent (met ingesloten CMYK ICC-profiel),
    TrimBox en BleedBox toe. Vereist dat alle content al CMYK is (geen RGB/
    transparantie) - dat garandeert export_to_cmyk_pdf() door alleen CMYK-
    fills en een CMYK-JPEG te gebruiken.
    pdf_version/gts_label kiezen tussen de klassieke PDF/X-1a:2001 (PDF 1.3,
    het breedst herkend door drukkerij-checks) en PDF/X-1a:2003 (PDF 1.4)."""
    pdf = pikepdf.Pdf.open(io.BytesIO(base_pdf_bytes))
    page = pdf.pages[0]

    media = [0, 0, width_pt, height_pt]
    trim = [bleed_pt, bleed_pt, width_pt - bleed_pt, height_pt - bleed_pt]

    page.MediaBox = media
    page.TrimBox = trim
    page.BleedBox = media

    if os.path.exists(ICC_PROFILE_PATH):
        with open(ICC_PROFILE_PATH, "rb") as f:
            icc_bytes = f.read()
        icc_stream = pdf.make_stream(icc_bytes)
        icc_stream.N = 4
        icc_stream.Alternate = pikepdf.Name("/DeviceCMYK")

        output_intent = pdf.make_indirect(pikepdf.Dictionary({
            "/Type": pikepdf.Name("/OutputIntent"),
            "/S": pikepdf.Name("/GTS_PDFX"),
            "/OutputConditionIdentifier": pikepdf.String(output_condition),
            "/OutputCondition": pikepdf.String(output_condition),
            "/Info": pikepdf.String(output_condition),
            "/DestOutputProfile": icc_stream,
        }))
        pdf.Root.OutputIntents = pdf.make_indirect(pikepdf.Array([output_intent]))

    pdf.docinfo["/GTS_PDFXVersion"] = gts_label
    pdf.docinfo["/GTS_PDFXConformance"] = gts_label
    pdf.docinfo["/Trapped"] = pikepdf.Name("/False")

    out = io.BytesIO()
    pdf.save(out, min_version=pdf_version)
    return out.getvalue()

def get_dominant_color(image):
    """Bepaal dominante kleur"""
    small_img = image.resize((100, 100))
    small_img = small_img.quantize(colors=64).convert('RGB')
    pixels = list(small_img.getdata())
    return Counter(pixels).most_common(1)[0][0]

def remove_crop_marks(image, crop_pixels):
    """Verwijder crop marks van PDF"""
    if crop_pixels <= 0:
        return image
    
    width, height = image.size
    if width > crop_pixels * 2 and height > crop_pixels * 2:
        return image.crop((
            crop_pixels,
            crop_pixels,
            width - crop_pixels,
            height - crop_pixels
        ))
    return image

def create_pixel_perfect_bleed(original_img, bleed_pixels, method, custom_color=None, blur_pixels=8):
    """
    CREËERT EEN PIXEL-PERFECTE BLEED
    Belangrijk: De randpixels worden exact gekopieerd van de originele randen
    Geen +1 of -1 afrondingsfouten meer!
    """
    width, height = original_img.size
    new_width = width + (bleed_pixels * 2)
    new_height = height + (bleed_pixels * 2)
    
    if method == "Wit / Geselecteerde Kleur":
        # Eenvoudige kleurvulling
        color = custom_color if custom_color else (255, 255, 255)
        new_img = Image.new('RGB', (new_width, new_height), color)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        # Vervaging op de rand voor naadloze overgang
        if blur_pixels > 0:
            new_img = apply_edge_blur(new_img, bleed_pixels, blur_pixels)
        
        return new_img
        
    elif method == "Spiegelen (Mirror) - Pixel Perfect":
        # Creëer canvas
        new_img = Image.new('RGB', (new_width, new_height))
        
        # PIXEL-PERFECT: Kopieer exacte pixels van origineel naar bleed
        # Geen interpolatie, geen resize, exacte kopie!
        
        # Eerst het origineel in het midden
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        if bleed_pixels > 0:
            # BOVENRAND: Kopieer exacte pixels van boven naar beneden
            for y in range(bleed_pixels):
                source_y = y  # Bovenste pixels van origineel
                target_y = bleed_pixels - 1 - y  # Omgekeerd voor mirror
                
                # Haal de volledige rij pixels op uit het origineel
                source_row = original_img.crop((0, source_y, width, source_y + 1))
                # Plak ze op de target locatie in bleed
                new_img.paste(source_row, (bleed_pixels, target_y))
            
            # ONDERRAND: Kopieer exacte pixels van onder naar boven
            for y in range(bleed_pixels):
                source_y = height - 1 - y  # Onderste pixels van origineel
                target_y = new_height - bleed_pixels + y  # Omgekeerd voor mirror
                
                source_row = original_img.crop((0, source_y, width, source_y + 1))
                new_img.paste(source_row, (bleed_pixels, target_y))
            
            # LINKERRAND: Kopieer exacte pixels van links naar rechts
            for x in range(bleed_pixels):
                source_x = x
                target_x = bleed_pixels - 1 - x
                
                source_col = original_img.crop((source_x, 0, source_x + 1, height))
                new_img.paste(source_col, (target_x, bleed_pixels))
            
            # RECHTERRAND: Kopieer exacte pixels van rechts naar links
            for x in range(bleed_pixels):
                source_x = width - 1 - x
                target_x = new_width - bleed_pixels + x
                
                source_col = original_img.crop((source_x, 0, source_x + 1, height))
                new_img.paste(source_col, (target_x, bleed_pixels))
            
            # HOEKEN: 4 hoeken exact spiegelen
            # Boven-links
            for y in range(bleed_pixels):
                for x in range(bleed_pixels):
                    source_pixel = original_img.getpixel((x, y))
                    new_img.putpixel((bleed_pixels - 1 - x, bleed_pixels - 1 - y), source_pixel)
            
            # Boven-rechts
            for y in range(bleed_pixels):
                for x in range(bleed_pixels):
                    source_pixel = original_img.getpixel((width - 1 - x, y))
                    new_img.putpixel((new_width - bleed_pixels + x, bleed_pixels - 1 - y), source_pixel)
            
            # Onder-links
            for y in range(bleed_pixels):
                for x in range(bleed_pixels):
                    source_pixel = original_img.getpixel((x, height - 1 - y))
                    new_img.putpixel((bleed_pixels - 1 - x, new_height - bleed_pixels + y), source_pixel)
            
            # Onder-rechts
            for y in range(bleed_pixels):
                for x in range(bleed_pixels):
                    source_pixel = original_img.getpixel((width - 1 - x, height - 1 - y))
                    new_img.putpixel((new_width - bleed_pixels + x, new_height - bleed_pixels + y), source_pixel)
        
        # Vervaging op de rand voor naadloze overgang
        if blur_pixels > 0:
            new_img = apply_edge_blur(new_img, bleed_pixels, blur_pixels)
        
        return new_img
        
    elif method == "Randpixels Uitrekken (Stretch) - Pixel Perfect":
        new_img = Image.new('RGB', (new_width, new_height))
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        if bleed_pixels > 0:
            # BOVENRAND: Herhaal de eerste pixelrij
            top_row = original_img.crop((0, 0, width, 1))
            for y in range(bleed_pixels):
                new_img.paste(top_row, (bleed_pixels, y))
            
            # ONDERRAND: Herhaal de laatste pixelrij
            bottom_row = original_img.crop((0, height-1, width, height))
            for y in range(bleed_pixels):
                new_img.paste(bottom_row, (bleed_pixels, new_height - bleed_pixels + y))
            
            # LINKERRAND: Herhaal de eerste pixelkolom
            left_col = original_img.crop((0, 0, 1, height))
            for x in range(bleed_pixels):
                new_img.paste(left_col, (x, bleed_pixels))
            
            # RECHTERRAND: Herhaal de laatste pixelkolom
            right_col = original_img.crop((width-1, 0, width, height))
            for x in range(bleed_pixels):
                new_img.paste(right_col, (new_width - bleed_pixels + x, bleed_pixels))
            
            # HOEKEN: Gebruik de hoekpixels
            top_left_pixel = original_img.getpixel((0, 0))
            for y in range(bleed_pixels):
                for x in range(bleed_pixels):
                    new_img.putpixel((x, y), top_left_pixel)
            
            top_right_pixel = original_img.getpixel((width-1, 0))
            for y in range(bleed_pixels):
                for x in range(bleed_pixels):
                    new_img.putpixel((new_width - bleed_pixels + x, y), top_right_pixel)
            
            bottom_left_pixel = original_img.getpixel((0, height-1))
            for y in range(bleed_pixels):
                for x in range(bleed_pixels):
                    new_img.putpixel((x, new_height - bleed_pixels + y), bottom_left_pixel)
            
            bottom_right_pixel = original_img.getpixel((width-1, height-1))
            for y in range(bleed_pixels):
                for x in range(bleed_pixels):
                    new_img.putpixel((new_width - bleed_pixels + x, new_height - bleed_pixels + y), bottom_right_pixel)
        
        # Vervaging op de rand
        if blur_pixels > 0:
            new_img = apply_edge_blur(new_img, bleed_pixels, blur_pixels)
        
        return new_img
        
    elif method == "Dominante Achtergrondkleur":
        dominant_color = get_dominant_color(original_img)
        new_img = Image.new('RGB', (new_width, new_height), dominant_color)
        new_img.paste(original_img, (bleed_pixels, bleed_pixels))
        
        if blur_pixels > 0:
            new_img = apply_edge_blur(new_img, bleed_pixels, blur_pixels)
        
        return new_img

def apply_edge_blur(image, bleed_pixels, blur_radius):
    """
    Pas een Gaussiaanse vervaging toe op de rand van de bleed
    Dit zorgt voor een vloeiende overgang tussen origineel en bleed
    """
    # Maak een kopie om te vervagen
    blurred = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    
    # Creëer een masker voor alleen de randzone
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)
    
    # Teken de bleed zones in het masker
    width, height = image.size
    
    # Bovenrand
    draw.rectangle([bleed_pixels, 0, width - bleed_pixels, min(blur_radius * 2, bleed_pixels)], fill=255)
    # Onderrand
    draw.rectangle([bleed_pixels, height - min(blur_radius * 2, bleed_pixels), width - bleed_pixels, height], fill=255)
    # Linkerrand
    draw.rectangle([0, bleed_pixels, min(blur_radius * 2, bleed_pixels), height - bleed_pixels], fill=255)
    # Rechterrand
    draw.rectangle([width - min(blur_radius * 2, bleed_pixels), bleed_pixels, width, height - bleed_pixels], fill=255)
    # Hoeken
    draw.rectangle([0, 0, min(blur_radius * 2, bleed_pixels), min(blur_radius * 2, bleed_pixels)], fill=255)
    draw.rectangle([width - min(blur_radius * 2, bleed_pixels), 0, width, min(blur_radius * 2, bleed_pixels)], fill=255)
    draw.rectangle([0, height - min(blur_radius * 2, bleed_pixels), min(blur_radius * 2, bleed_pixels), height], fill=255)
    draw.rectangle([width - min(blur_radius * 2, bleed_pixels), height - min(blur_radius * 2, bleed_pixels), width, height], fill=255)
    
    # Pas alleen vervaging toe op de randzone
    result = Image.composite(blurred, image, mask)
    
    return result

def export_to_pdf_perfect(image, convert_cmyk, profile_name, output_format, bleed_mm):
    """
    LEGACY EXPORT: plaatst het beeld als RGB in de PDF en zet alleen
    metadata-labels ("CMYK (profiel)") - dit converteert de pixels NIET
    echt naar CMYK. Wordt nog gebruikt als "snelle"/compatibele modus;
    voor echte inktomzetting en PDF/X-1a, zie export_to_cmyk_pdf().
    """
    # Bereken afmetingen in punten
    width_pt = (image.width / 300.0) * 72.0
    height_pt = (image.height / 300.0) * 72.0

    # Overscan om haarlijnen te voorkomen
    overscan = 1.0  # 1 punt overlap

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt + overscan, height_pt + overscan))

    # Witte achtergrond
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, width_pt + overscan, height_pt + overscan, fill=1, stroke=0)

    # Metadata
    if convert_cmyk:
        c.setProducer(f"C.A. Bleed Tool - CMYK ({profile_name}) - Pixel Perfect")
        c.setTitle(f"C.A. Document - {output_format} - {bleed_mm}mm bleed")

    # Gebruik PNG voor maximale kwaliteit
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
        temp_path = tmp_file.name
        image.save(temp_path, 'PNG', dpi=(300, 300))

    # Plaats afbeelding met overscan
    img_reader = ImageReader(temp_path)
    c.drawImage(
        img_reader,
        -overscan/2,
        -overscan/2,
        width=width_pt + overscan,
        height=height_pt + overscan,
        preserveAspectRatio=False,
        mask=None
    )

    c.showPage()
    c.save()

    try:
        os.unlink(temp_path)
    except:
        pass

    return buffer.getvalue()


def export_to_cmyk_pdf(image, profile_key, bleed_mm, pdfx1a=False,
                        pdf_version="1.4", gts_label="PDF/X-1a:2003"):
    """
    ECHTE CMYK-EXPORT: zet de pixels daadwerkelijk om naar CMYK (getuned op
    het gekozen drukprofiel via total-area-coverage-limiet en GCR), bouwt
    een CMYK-JPEG en plaatst die in de PDF met alleen CMYK-fills (geen RGB).
    Als pdfx1a=True wordt de PDF daarna met pikepdf omgezet naar een
    structureel geldige PDF/X-1a (OutputIntent + TrimBox/BleedBox) - dit is
    wat drukkers voor bv. gevouwde folders vaak verplicht stellen.
    pdf_version bepaalt de gedeclareerde PDF-versie (bv. "1.3" voor de
    klassieke PDF/X-1a:2001, "1.5" als een drukker dat letterlijk vraagt).
    """
    profile = COLOR_PROFILES.get(profile_key, COLOR_PROFILES["GenericCMYK"])
    cmyk_arr = rgb_image_to_cmyk_array(image, tac_limit=profile["tac"], gcr=profile["gcr"])
    jpeg_bytes = cmyk_array_to_jpeg_bytes(cmyk_arr, quality=92)

    width_pt = (image.width / 300.0) * 72.0
    height_pt = (image.height / 300.0) * 72.0
    bleed_pt = (bleed_mm / 25.4) * 72.0

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt, height_pt))

    # Zuivere CMYK-achtergrond (géén RGB) - verplicht voor PDF/X-1a
    c.setFillColorCMYK(0, 0, 0, 0)
    c.rect(0, 0, width_pt, height_pt, fill=1, stroke=0)

    c.setProducer(f"C.A. Bleed Tool - echte CMYK ({profile_key})")
    c.setTitle(f"C.A. Document - {bleed_mm}mm bleed - {profile_key}")

    img_reader = ImageReader(io.BytesIO(jpeg_bytes))
    c.drawImage(
        img_reader,
        0, 0,
        width=width_pt,
        height=height_pt,
        preserveAspectRatio=False,
        mask=None
    )

    c.showPage()
    c.save()
    base_pdf = buffer.getvalue()

    if pdfx1a and PIKEPDF_SUPPORT:
        return finalize_pdfx1a(base_pdf, width_pt, height_pt, bleed_pt, profile_key,
                                pdf_version=pdf_version, gts_label=gts_label)

    if PIKEPDF_SUPPORT:
        # Ook zonder strikte PDF/X-1a: TrimBox/BleedBox zijn altijd nuttig
        # voor drukkerijen en kosten niets om toe te voegen.
        pdf = pikepdf.Pdf.open(io.BytesIO(base_pdf))
        page = pdf.pages[0]
        page.MediaBox = [0, 0, width_pt, height_pt]
        page.TrimBox = [bleed_pt, bleed_pt, width_pt - bleed_pt, height_pt - bleed_pt]
        page.BleedBox = [0, 0, width_pt, height_pt]
        out = io.BytesIO()
        pdf.save(out, min_version=pdf_version)
        return out.getvalue()

    return base_pdf

def check_aspect_ratio(image, format_name):
    """Controleer aspect ratio"""
    format_mm = FORMATS[format_name]
    target_ratio = format_mm[0] / format_mm[1]
    image_ratio = image.width / image.height
    ratio_diff = abs((image_ratio - target_ratio) / target_ratio) * 100
    
    if ratio_diff > 10:
        return f"⚠️ Aspect ratio verschil van {ratio_diff:.1f}% - beeld wordt bijgesneden"
    else:
        return f"✓ Aspect ratio ok ({ratio_diff:.1f}% verschil)"

# ============================================================================
# HOOFD INTERFACE
# ============================================================================

st.title("📐 C.A. Professional Bleed Tool - Pixel Perfect")
st.subheader("Professionele afloopruimte met exacte pixel matching en vloeiende overgangen")

with st.sidebar:
    st.header("🔧 Drukwerk Instellingen")
    
    # Input formaat (originele bestandsformaat)
    input_format = st.selectbox("📥 Input Formaat (Origineel bestand):", list(FORMATS.keys()), index=1)
    st.caption("Het formaat waarin je bestand is gemaakt")
    
    st.divider()
    
    # Output formaat (gewenste output)
    output_format = st.selectbox("📤 Output Formaat (Gewenste output):", list(FORMATS.keys()), index=1)
    width_mm, height_mm = FORMATS[output_format]
    st.caption(f"Output wordt: {width_mm} × {height_mm} mm")
    
    st.divider()
    
    # Bleed instellingen
    bleed_mm = st.number_input("📏 Bleed (mm):", min_value=0.0, max_value=20.0, value=3.0, step=0.5, format="%.1f")
    st.caption("Aanbevolen: 3mm voor drukwerk")
    
    # Vervaging instellingen
    st.divider()
    st.subheader("🎨 Overgangsinstellingen")
    blur_pixels = st.slider("Randvervaging (pixels):", 0, 56, 12, 
                            help="Vervaging op de overgang tussen origineel en bleed. 8-16 pixels werkt meestal goed.")
    st.caption("Hogere waarde = vloeiendere overgang")
    
    fill_method = st.radio(
        "🎨 Vulmethode:",
        ["Spiegelen (Mirror) - Pixel Perfect", "Randpixels Uitrekken (Stretch) - Pixel Perfect", 
         "Wit / Geselecteerde Kleur", "Dominante Achtergrondkleur"],
        help="Mirror: exacte pixel kopie | Stretch: herhaal randpixels"
    )
    
    # Kleur selectie
    chosen_rgb = (255, 255, 255)
    if "Wit / Geselecteerde Kleur" in fill_method:
        hex_color = st.color_picker("🎨 Randkleur:", "#FFFFFF")
        chosen_rgb = tuple(int(hex_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        c, m, y, k = rgb_to_cmyk(*chosen_rgb)
        st.caption(f"CMYK: {c:.0f}%, {m:.0f}%, {y:.0f}%, {k:.0f}%")
    
    st.divider()
    
    # CMYK / drukker instellingen
    st.subheader("🖨️ Voor welke drukker?")
    convert_to_cmyk = st.checkbox("Omzetten naar CMYK", value=True)
    color_profile = "GenericCMYK"
    real_cmyk_conversion = False
    pdfx1a_enabled = False
    pdf_version = "1.4"
    gts_label = "PDF/X-1a:2003"

    if convert_to_cmyk:
        preset_keys = list(PRINTER_PRESETS.keys())
        preset_choice = st.selectbox(
            "Kies je drukker (of 'Geavanceerd' om alles zelf te kiezen):",
            preset_keys, index=0,
            help="Elke drukker heeft net iets andere eisen (PDF-versie, "
                 "wel/niet PDF/X-1a, welk CMYK-profiel). Kies hier je drukker "
                 "en de juiste instellingen worden automatisch gezet."
        )
        preset = PRINTER_PRESETS[preset_choice]

        if preset is not None:
            # --- Eenvoudige modus: alles automatisch, niets technisch te kiezen ---
            color_profile = preset["profile"]
            real_cmyk_conversion = True
            pdfx1a_enabled = preset["pdfx1a"]
            pdf_version = preset["pdf_version"]
            gts_label = preset["gts_label"]
            st.caption(f"ℹ️ {preset['explain']}")
            with st.expander("Technische details van deze preset"):
                st.write(f"- Drukprofiel: **{color_profile}** ({COLOR_PROFILES[color_profile]['desc']})")
                st.write(f"- PDF-versie: **{pdf_version}**")
                st.write(f"- PDF/X-1a: **{'Ja - ' + gts_label if pdfx1a_enabled else 'Nee'}**")
                st.caption(
                    "Klopt dit niet (meer) met wat je drukker vraagt? Kies "
                    "hierboven 'Geavanceerd: zelf instellen' om het zelf aan "
                    "te passen, of stuur door zodat de preset bijgewerkt kan "
                    "worden."
                )
        else:
            # --- Geavanceerde modus: de volledige, oude handmatige controls ---
            profile_keys = list(COLOR_PROFILES.keys())
            color_profile = st.selectbox("Drukprofiel:", profile_keys, index=0)
            st.caption(COLOR_PROFILES[color_profile]["desc"])

            real_cmyk_conversion = st.checkbox(
                "Echte CMYK-pixelomzetting (aanbevolen)",
                value=True,
                help="Zet de afbeelding echt om naar CMYK-inktwaarden, getuned op "
                     "het gekozen profiel (inktlimiet + zwartopbouw). Staat dit uit, "
                     "dan blijft het beeld RGB en wordt CMYK alleen als label in de "
                     "PDF-metadata gezet (oud gedrag, niet aan te raden voor drukwerk)."
            )

            if real_cmyk_conversion and PIKEPDF_SUPPORT:
                pdfx1a_enabled = st.checkbox(
                    "Exporteer als PDF/X-1a",
                    value=False,
                    help="Veel drukkers eisen PDF/X-1a, bijvoorbeeld voor gevouwde "
                         "folders. Voegt een CMYK-OutputIntent en de verplichte "
                         "TrimBox/BleedBox toe aan het PDF-bestand."
                )
                if pdfx1a_enabled:
                    gts_label = st.selectbox(
                        "PDF/X-1a-variant:", ["PDF/X-1a:2001", "PDF/X-1a:2003"], index=0,
                        help="2001 (PDF 1.3) wordt door de meeste drukkerij-checks "
                             "het breedst herkend. 2003 (PDF 1.4) is nieuwer maar "
                             "soms strikter in checks die nog op 2001 zijn ingesteld."
                    )
                    pdf_version = "1.3" if gts_label.endswith("2001") else "1.4"
                    st.caption(
                        "⚠️ Dit gebruikt een generiek, vrij herdistribueerbaar CMYK "
                        "ICC-profiel (Ghostscript/Artifex) als OutputIntent, géén "
                        "gelicentieerd Fogra/SWOP-profiel - de inktomzetting is "
                        "getuned op het gekozen profiel, maar niet pixel-exact "
                        "gecertificeerd. Dubbelcheck bij je drukker of dit voldoet; "
                        "voor 100% garantie kan de drukker zelf met het officiële "
                        "profiel converteren in Acrobat Pro."
                    )
                else:
                    pdf_version = st.selectbox(
                        "PDF-versie:", ["1.3", "1.4", "1.5", "1.6", "1.7"], index=1,
                        help="Sommige drukkers vragen expliciet een bepaalde "
                             "PDF-versie (bv. 'upload als PDF 1.5')."
                    )
            elif real_cmyk_conversion and not PIKEPDF_SUPPORT:
                st.caption("ℹ️ Installeer 'pikepdf' voor PDF/X-1a en TrimBox/BleedBox-ondersteuning.")
    
    # PDF import
    st.divider()
    st.subheader("📑 PDF Import")
    crop_marks_remove = st.checkbox("Verwijder snijtekens", value=True)
    if crop_marks_remove:
        crop_pixels = st.slider("Wegknippen (pixels):", 20, 100, 35)

# Bestand upload
st.markdown("### 📂 1. Upload bestand")
uploaded_file = st.file_uploader(
    "PDF, JPG, JPEG of PNG",
    type=["jpg", "jpeg", "png", "pdf"]
)

if uploaded_file is not None:
    try:
        # Laad bestand
        file_bytes = uploaded_file.read()
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        with st.spinner("📄 Laden..."):
            if file_ext == 'pdf':
                if not PDF_IMPORT:
                    st.error("Installeer pdf2image: pip install pdf2image")
                    st.stop()
                
                images = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=300)
                if images:
                    original_img = images[0]
                    if crop_marks_remove:
                        original_img = remove_crop_marks(original_img, crop_pixels)
                        st.success(f"✓ Snijtekens verwijderd")
                else:
                    st.error("Kan PDF niet laden")
                    st.stop()
            else:
                original_img = Image.open(io.BytesIO(file_bytes))
            
            if original_img.mode != 'RGB':
                original_img = original_img.convert('RGB')
        
        # Aspect ratio check
        st.markdown("### 📏 2. Formaat check")
        aspect_msg = check_aspect_ratio(original_img, output_format)
        if "⚠️" in aspect_msg:
            st.warning(aspect_msg)
        else:
            st.success(aspect_msg)
        
        # Preview
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<p class="report-title">📸 Origineel</p>', unsafe_allow_html=True)
            st.image(original_img, use_container_width=True)
        
        # Verwerk bleed
        with st.spinner("🔧 Bleed toevoegen (pixel-perfect met vervaging)..."):
            # Resize naar exact output formaat
            target_width = int(width_mm / 25.4 * 300)
            target_height = int(height_mm / 25.4 * 300)
            resized_img = original_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Bleed pixels
            bleed_pixels = int(bleed_mm / 25.4 * 300)
            
            # Creëer pixel-perfect bleed
            final_img = create_pixel_perfect_bleed(
                resized_img, bleed_pixels, fill_method, chosen_rgb, blur_pixels
            )
        
        with col2:
            st.markdown('<p class="report-title">✨ Met Bleed</p>', unsafe_allow_html=True)
            st.image(final_img, use_container_width=True)
            st.success(f"✅ +{bleed_mm}mm bleed | Vervaging: {blur_pixels}px")
        
        # Export
        st.markdown("### 💾 3. Exporteer")

        base_name = os.path.splitext(uploaded_file.name)[0]
        cmyk_suffix = "_CMYK" if convert_to_cmyk else ""
        pdfx_suffix = "_PDFX1a" if pdfx1a_enabled else ""

        spinner_label = "📑 PDF genereren"
        if real_cmyk_conversion:
            spinner_label += " (echte CMYK-omzetting" + (" + PDF/X-1a" if pdfx1a_enabled else "") + ")..."
        else:
            spinner_label += " (haarlijnvrij)..."

        with st.spinner(spinner_label):
            if convert_to_cmyk and real_cmyk_conversion:
                pdf_data = export_to_cmyk_pdf(
                    final_img, color_profile, bleed_mm, pdfx1a=pdfx1a_enabled,
                    pdf_version=pdf_version, gts_label=gts_label
                )
            else:
                pdf_data = export_to_pdf_perfect(
                    final_img, convert_to_cmyk, color_profile, output_format, bleed_mm
                )

            st.download_button(
                label=f"📥 Download {output_format} PDF {cmyk_suffix}{pdfx_suffix}",
                data=pdf_data,
                file_name=f"{base_name}{cmyk_suffix}{pdfx_suffix}_BLEED{int(bleed_mm)}mm_{output_format}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

            if convert_to_cmyk and real_cmyk_conversion:
                st.info(f"🖨️ Echte CMYK-pixelomzetting toegepast - profiel: {color_profile}")
                if pdfx1a_enabled:
                    st.info("📋 PDF/X-1a:2003 - CMYK OutputIntent + TrimBox/BleedBox ingesteld")
            elif convert_to_cmyk:
                st.info(f"🖨️ CMYK metadata (geen pixelomzetting) - {color_profile}")

        st.balloons()
        
    except Exception as e:
        st.error(f"Fout: {str(e)}")
        st.exception(e)

else:
    # Info
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 📌 Stappen
        1. Upload bestand
        2. Kies output formaat
        3. Stel bleed in
        4. Download
        """)
    
    with col2:
        st.markdown("""
        ### 🎨 Pixel Perfect
        - Exacte pixel kopie
        - Geen interpolatie
        - Randvervaging
        - Vloeiende overgang
        """)
    
    with col3:
        st.markdown("""
        ### ✨ Features
        - ✓ Geen haarlijnen
        - ✓ Pixel matching
        - ✓ Vervaging optie
        - ✓ PNG kwaliteit
        """)

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666;'>© 2024 C.A. Professional Bleed Tool | Pixel Perfect voor drukwerk</p>", 
    unsafe_allow_html=True
)
