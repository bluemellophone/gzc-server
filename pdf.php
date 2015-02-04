<?php
    $content = '
	<!DOCTYPE html>
	<html>
		' . $content . '
		<link type="text/css" rel="stylesheet" href="http://' . $_SERVER['HTTP_HOST'] . '/static/css/printable.css"/>
	<html>';

	file_put_contents($_SERVER["DOCUMENT_ROOT"] . '/pdfs/' . $nonce_attachment . '.html', $content);
	// Convert HTML to PDF
	
	if(__DEBUG_SERVER__)
	{
		$script = '/usr/local/bin/wkhtmltopdf';
	}
	else
	{
		$script = '/usr/local/bin/wkhtmltopdf';
	}
	shell_exec($script . ' -s Letter -B 0 -L 0 -R 0 -T 0 --zoom 1.1 ../pdfs/' . $nonce_attachment . '.html ../pdfs/' . $nonce_attachment . '-uncompressed.pdf');
	
	// GhostScript PDF file to drastically decrease the PDF's filesize
	if(__DEBUG_SERVER__)
	{
		$script = '/opt/local/bin/gs';
	}
	else
	{
		$script = '/usr/bin/gs';
	}
	shell_exec($script . ' -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dNOPAUSE -dQUIET -dBATCH -sOutputFile=../pdfs/' . $nonce_attachment . '.pdf ../pdfs/' . $nonce_attachment . '-uncompressed.pdf');
	// Remove uncompressed version of the PDF
	shell_exec('rm -rf ../pdfs/' . $nonce_attachment . '-uncompressed.pdf');
	shell_exec('rm -rf ../pdfs/' . $nonce_attachment . '.html');		
?>